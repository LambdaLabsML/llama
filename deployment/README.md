### Step one: launch instances

We will use Lambda cloud as an example. You can manually launch instances from the [Cloud Dashboard](https://cloud.lambdalabs.com/instances), or using the [Cloud API](https://docs.lambdalabs.com/cloud/launch-instance-api/). In the later case, you need to generate an API key, create a payload `request.json`, and then run the following command:

```
API-KEY=you-api-key
curl -u $API-KEY: https://cloud.lambdalabs.com/api/v1/instance-operations/launch -d @request.json -H "Content-Type: application/json" | jq .
```

### Step two: step up the instances

After the instances are launched (the `STATUS` column shows a green tick), we can move on to get the instances set up for running LLAMA distributedly:

- Give the head node passwordless access to all other nodes.
- Disable Infiniband for `NCCL` (since Lambda's on-demand instance doesn't support Infiniband).
- Set up a shared NFS.
- Clone the LLAMA repo and install dependencies.

We provide a shell script `setup_nodes` that automate these jobs. You need to set the variables in the `config.sh` according to your own case:

```
LAMBDA_CLOUD_KEY="path-to-your-cloud-ssh-key"
HEAD_IP="head-node-public-ip"
WORKER_IP="worker-0-public-ip worker-1-public-ip"
```

Then run the setup_nodes.sh script:

```
./setup_nodes.sh
```

The `HEAD_IP` is the ip of the instance where you will set up NFS and launch distributed LLAMA inference jobs from. `WORKER_IP` is a string of space-separated IPs for the other instances.

NOTE: `setup_nodes.sh` will ask you to type `yes` and hit `enter` a few times. After that, you will have the minimal setup needed to run distributed PyTorch jobs (what LLAMA needs) on the cloud instances defined in the `config.sh` script.

### Step three: download pre-trained ckpts

### Step four: run LLAMA
