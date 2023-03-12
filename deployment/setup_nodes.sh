#!/bin/bash

source ./config.sh

ALL_IP=( $HEAD_IP "${WORKER_IP[@]}" )

echo "List of nodes: "
for IP in ${ALL_IP[*]}; do
    echo $IP
done

echo "Generate ssh keys on the head node ------------------------------"
ssh -i $LAMBDA_CLOUD_KEY ubuntu@$HEAD_IP "ssh-keygen -t rsa -N ''"

echo "Add public key to the all nodes ------------------------------"
for IP in ${ALL_IP[*]}; do
    ssh -i $LAMBDA_CLOUD_KEY ubuntu@$HEAD_IP "cat ~/.ssh/id_rsa.pub" | ssh -i $LAMBDA_CLOUD_KEY ubuntu@$IP "cat >> ~/.ssh/authorized_keys"
done

echo "Set NCCL_IB_DISABLE=1 for all nodes ------------------------------"
for IP in ${ALL_IP[*]}; do
    ssh -i $LAMBDA_CLOUD_KEY ubuntu@$IP "echo export NCCL_IB_DISABLE=1 >> .bashrc"
    ssh -i $LAMBDA_CLOUD_KEY ubuntu@$IP "echo NCCL_IB_DISABLE=1 | sudo tee -a /etc/environment"
done

echo "Let the head node ssh into the all nodes at least once so in the future it won't ask about fingerprint ------------------------------"
for IP in ${ALL_IP[*]}; do
    ssh -i $LAMBDA_CLOUD_KEY -t ubuntu@$HEAD_IP "echo exit | xargs ssh ubuntu@$IP"
done

echo "Set up NFS ------------------------------"
for IP in ${ALL_IP[*]}; do
    ssh -i $LAMBDA_CLOUD_KEY ubuntu@$IP "if [ ! -d shared ]; then mkdir shared; fi"
done

cat head-nfs-install.sh | sed "s/ [\\]//g" | ssh -i $LAMBDA_CLOUD_KEY ${HEAD_IP}

for IP in ${WORKER_IP[*]}; do
    ssh -i $LAMBDA_CLOUD_KEY ubuntu@$HEAD_IP "echo '/home/ubuntu/shared ${IP}(rw,sync,no_subtree_check)' | sudo tee -a /etc/exports"
done
ssh -i $LAMBDA_CLOUD_KEY ubuntu@$HEAD_IP "sudo systemctl restart nfs-kernel-server"
# echo "NFS set up on the head node"

for IP in ${WORKER_IP[*]}; do
    ssh -i $LAMBDA_CLOUD_KEY ubuntu@$IP "sudo mount ${HEAD_IP}:/home/ubuntu/shared /home/ubuntu/shared"
done

echo "NFS set up on the worker nodes"

echo "Clone repos into NFS ------------------------------"
ssh -i $LAMBDA_CLOUD_KEY ubuntu@$HEAD_IP "if [ ! -d /home/ubuntu/shared/llama ]; then git clone https://github.com/LambdaLabsML/llama.git /home/ubuntu/shared/llama; fi"
ssh -i $LAMBDA_CLOUD_KEY ubuntu@$HEAD_IP "if [ ! -d /home/ubuntu/shared/llama-dl ]; then git clone https://github.com/chuanli11/llama-dl.git /home/ubuntu/shared/llama-dl; fi"

echo "Install LLAMA dependencies (asynchronously) ------------------------------"
for IP in ${ALL_IP[*]}; do cat dependencies-install.sh | ssh -i $LAMBDA_CLOUD_KEY ${IP} & done

wait

echo "All instances are successfully set up 🥳🥳🥳🥳🥳🥳🥳🥳"