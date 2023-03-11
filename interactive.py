# Copyright (c) Meta Platforms, Inc. and affiliates.
# This software may be used and distributed according to the terms of the GNU General Public License version 3.

from typing import Tuple
import os
import sys
import torch
import fire
import time
import json
import torch.distributed as dist

from pathlib import Path

from fairscale.nn.model_parallel.initialize import initialize_model_parallel

from llama import ModelArgs, Transformer, Tokenizer, LLaMA


def setup_model_parallel(seed: int) -> Tuple[int, int]:
    if 'LOCAL_RANK' in os.environ:
        # Environment variables set by torch.distributed.launch or torchrun
        local_rank = int(os.environ['LOCAL_RANK'])
        world_size = int(os.environ['WORLD_SIZE'])
        world_rank = int(os.environ['RANK'])
    elif 'OMPI_COMM_WORLD_LOCAL_RANK' in os.environ:
        # Environment variables set by mpirun
        local_rank = int(os.environ['OMPI_COMM_WORLD_LOCAL_RANK'])
        world_size = int(os.environ['OMPI_COMM_WORLD_SIZE'])
        world_rank = int(os.environ['OMPI_COMM_WORLD_RANK'])
    else:
        import sys
        sys.exit("Can't find the evironment variables for local rank")

    torch.distributed.init_process_group(backend="nccl", rank=world_rank, world_size=world_size)
    initialize_model_parallel(world_size)
    torch.cuda.set_device(local_rank)

    # seed must be the same in all processes
    torch.manual_seed(seed)
    return local_rank, world_rank, world_size


def load(
    ckpt_dir: str,
    tokenizer_path: str,
    local_rank: int,
    world_rank: int,
    world_size: int,
    max_seq_len: int,
    max_batch_size: int,
) -> LLaMA:
    start_time = time.time()
    checkpoints = sorted(Path(ckpt_dir).glob("*.pth"))
    assert world_size == len(
        checkpoints
    ), f"Loading a checkpoint for MP={len(checkpoints)} but world size is {world_size}"

    ckpt_path = checkpoints[world_rank]
    print("Loading")
    checkpoint = torch.load(ckpt_path, map_location="cpu")
    with open(Path(ckpt_dir) / "params.json", "r") as f:
        params = json.loads(f.read())

    model_args: ModelArgs = ModelArgs(
        max_seq_len=max_seq_len, max_batch_size=max_batch_size, **params
    )
    tokenizer = Tokenizer(model_path=tokenizer_path)
    model_args.vocab_size = tokenizer.n_words
    torch.set_default_tensor_type(torch.cuda.HalfTensor)
    model = Transformer(model_args)
    torch.set_default_tensor_type(torch.FloatTensor)
    model.load_state_dict(checkpoint, strict=False)

    generator = LLaMA(model, tokenizer)
    print(f"Loaded in {time.time() - start_time:.2f} seconds")
    return generator


def main(
    ckpt_dir: str,
    tokenizer_path: str,
    temperature: float = 0.7,
    # top_p: float = 0.95,
    top_p: float = 0.0,
    top_k: int = 10,
    repetition_penalty: float = (1 / 0.85),
    max_seq_len: int = 2048,
    max_gen_len: int = 2000,
    max_batch_size: int = 1,
    seed: int = 1,
    count: int = 1,
    eos_w: float = 1.0,
):
    local_rank, world_rank, world_size = setup_model_parallel(seed)
    device = torch.device("cuda:{}".format(local_rank))
    # if world_rank > 0:
    #     sys.stdout = open(os.devnull, "w")

    print("\n")
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    print(json.dumps(dict(
        seed=seed,
        temp=temperature,
        top_p=top_p,
        top_k=top_k,
        repetition_penalty=repetition_penalty,
        max_seq_len=max_seq_len,
        max_gen_len=max_gen_len,
        eos_w=eos_w,
    )))
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")


    generator = load(
        ckpt_dir, tokenizer_path, local_rank, world_rank, world_size, max_seq_len, max_batch_size
    )

    while True:
        if world_rank == 0:
            prompt = input("Prompt >>> ")
            while not prompt:
                print('Prompt should not be empty!')
                prompt = input("Prompt >>> ")
            tensor = torch.tensor([ord(c) for c in prompt])
            tensor = tensor.to(device)
            for rank_recv in range(1, world_size):
                dist.send(tensor=tensor, dst=rank_recv)
                print('Sending prompt to Rank {}\n'.format(rank_recv))
            for rank_recv in range(1, world_size):
                dist.recv(tensor=tensor, src=rank_recv)
                recv_prompt = ''.join([chr(int(x)) for x in tensor])
                print('Received prompt {} from Rank {}\n'.format(recv_prompt, rank_recv))
        else:
            tensor = torch.empty(256)
            tensor = tensor.to(device)
            dist.recv(tensor=tensor, src=0)
            dist.send(tensor=tensor, dst=0)
            prompt = ''.join([chr(int(x)) for x in tensor])

        # prompt = "[Scene: Central Perk, Chandler, Joey, Phoebe, and Monica are there.]"

        i = 0
        while i < count or count <= 0:
            i += 1
            print(f"\n============== sample {i} =================\n")
            width = 0
            def callback(text):
                nonlocal width
                text = text.replace('\n', '\n\n')
                chars = []
                for i, c in enumerate(text):
                    if c == ' ' and width >= 60:
                        chars.append('\n')
                        width = 0
                    else:
                        width += 1
                        chars.append(c)
                        if c == '\n':
                            width = 0
                text = ''.join(chars)
                print(text, end='', flush=True)
            text, = generator.generate(
                [prompt], max_gen_len=max_gen_len, temperature=temperature, top_p=top_p, top_k=top_k, repetition_penalty=repetition_penalty, token_callback=callback, eos_w=eos_w
            )


if __name__ == "__main__":
    fire.Fire(main)
