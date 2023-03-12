echo "Upgrade PyTorch on Lambda Cloud so it supports torchrun" &&
pip install torch==1.13.1+cu116 --extra-index-url https://download.pytorch.org/whl/cu116 &&
pip install fire &&
pip install -e /home/ubuntu/shared/llama &&
pip install -r /home/ubuntu/shared/llama/requirements.txt