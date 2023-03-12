echo "Set head node's /home/ubuntu/shared folder as an NFS" &&
sudo apt install nfs-kernel-server &&
sudo chmod 777 /home/ubuntu/shared &&
for worker in ${WORKER_IP[*]}; do printf "/home/ubuntu/shared ${worker}(rw,sync,no_subtree_check)\n" | sudo tee -a /etc/exports; done &&
sudo systemctl restart nfs-kernel-server &&
echo "NFS set up on the head node"