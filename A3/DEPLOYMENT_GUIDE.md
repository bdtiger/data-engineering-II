# 📚 COMPREHENSIVE DEPLOYMENT GUIDE: Assignment 3

## Table of Contents
1. [The Big Picture](#big-picture)
2. [Task 1: CloudInit Only](#task-1-cloudinit-only)
3. [Task 2: CloudInit + Docker](#task-2-cloudinit--docker)
4. [Task 3: CloudInit + Ansible](#task-3-cloudinit--ansible)
5. [Task 4: Git Hooks CI/CD](#task-4-git-hooks-cicd)
6. [CloudInit vs Ansible](#cloudinit-vs-ansible)
7. [Master Summary](#master-summary)
8. [Quick Reference](#quick-reference)

---

## Big Picture

### How Everything Connects

```
👤 You (Local Machine)
    ↓
    SSH into Client VM
    ↓
💻 Client VM (Ubuntu)
    ↓
    Run: python3 start_instance.py
    ↓
    OpenStack Python API (Nova Client)
    ↓
☁️ OpenStack Cloud Infrastructure
    ↓
    Creates VM with CloudInit script
    ↓
🖥️ Production VM (Automatically Configured)
    ↓
    CloudInit runs setup script
    ↓
    (Optional) Ansible orchestration
    ↓
    Application Ready!
    ↓
http://VM-IP:5100/predictions
```

---

## Task 1: CloudInit Only

### What Problem Does This Solve?

**Traditional approach**: Manually SSH into a VM and run installation commands
- ❌ Time-consuming
- ❌ Error-prone
- ❌ Hard to reproduce

**CloudInit solution**: Automate the entire setup at VM boot time
- ✅ Automatic
- ✅ Reproducible
- ✅ Fast deployment

### Architecture

Single VM, all services running directly (no containers):
- Flask web server (port 5100)
- RabbitMQ message broker (port 5672)
- Celery workers (background task executors)

### Code Walkthrough - How It Works

#### Step 1: OpenStack API Client (`start_instance.py`)

```python
# 1. AUTHENTICATE with OpenStack cloud
auth = loader.load_from_options(
    auth_url=env['OS_AUTH_URL'],           # e.g., https://east-1.cloud.snic.se:5000
    username=env['OS_USERNAME'],           # Your username
    password=env['OS_PASSWORD'],           # Your API password
    project_name=env['OS_PROJECT_NAME']    # Your project
)
sess = session.Session(auth=auth)
nova = client.Client('2.1', session=sess)  # Create Nova client
print("user authorization completed.")
```

**What happens:**
- Authenticates with OpenStack using Keystone identity service
- Creates a Nova client to interact with compute resources

#### Step 2: Load CloudInit Configuration

```python
# 2. READ the CloudInit script
cfg_file_path = os.getcwd() + '/cloud-cfg.txt'
if os.path.isfile(cfg_file_path):
    userdata = open(cfg_file_path)  # Read the script
else:
    sys.exit("cloud-cfg.txt not found")
```

**What happens:**
- Opens `cloud-cfg.txt` which contains all the setup commands
- This script will automatically run when the VM boots

#### Step 3: Create VM with CloudInit

```python
# 3. CREATE VM with the CloudInit script
instance = nova.servers.create(
    name="arnab_prod_server_without_docker",
    image=image,                    # Ubuntu 22.04 image
    flavor=flavor,                  # ssc.medium (VM size)
    key_name='de1-course-snic-key', # SSH key pair
    userdata=userdata,              # ← CloudInit script!
    nics=nics,                      # Network configuration
    security_groups=secgroups       # Firewall rules
)
```

**What happens:**
- OpenStack creates a new VM with specified properties
- **IMPORTANT**: `userdata=userdata` passes the CloudInit script to the VM
- CloudInit will automatically execute the script when VM boots

#### Step 4: Wait for VM to Be Ready

```python
# 4. WAIT for VM to finish booting
inst_status = instance.status  # Initially: "BUILD"
while inst_status == 'BUILD':
    print(f"Instance is in {inst_status} state, waiting...")
    time.sleep(5)
    instance = nova.servers.get(instance.id)
    inst_status = instance.status  # Check status again
```

**What happens:**
- Polls OpenStack API every 5 seconds
- Waits until VM status changes from "BUILD" to "ACTIVE"
- Then CloudInit script starts executing

### CloudInit Script (`cloud-cfg.txt`)

```yaml
#cloud-config                          # ← CloudInit format identifier

apt_update: true                        # Update package manager
apt_upgrade: true                       # Upgrade all packages

packages:                               # Install these packages
 - python3-pip                          # Python package manager
 - python3-dev                          # Python development files
 - build-essential                      # Compiler tools
 - rabbitmq-server                      # Message broker (RabbitMQ)

runcmd:                                 # Run these commands
 # Install Python packages
 - pip3 install "celery" "tensorflow==2.10.0" "flask==2.3.1" "numpy<2.0"
 
 # Clone the application repository
 - git clone https://github.com/sztoor/model_serving.git 
 
 # Start Celery worker (background task executor)
 - celery --workdir=/model_serving/single_server_without_docker/production_server \
           -A workerA worker --detach --loglevel=debug --concurrency=1 -n wkr1@backend
 
 # Start Flask web server (application frontend)
 - python3 /model_serving/single_server_without_docker/production_server/app.py \
           --host=0.0.0.0 --port=5100 &
```

### Execution Timeline

1. ✅ VM boots up
2. ✅ CloudInit reads `#cloud-config` format
3. ✅ Updates APT package manager
4. ✅ Installs RabbitMQ (message broker)
5. ✅ Installs Python packages (Celery, TensorFlow, Flask)
6. ✅ Clones git repository
7. ✅ Starts Celery worker listening to RabbitMQ
8. ✅ Starts Flask web server on port 5100
9. ✅ Application is now ready!

### User Request Flow

```
User (your browser) → http://Production-VM-IP:5100/predictions
            ↓
        Flask app.py receives POST request
            ↓
        get_predictions.delay() → sends task to RabbitMQ
            ↓
        RabbitMQ queues the message
            ↓
        Celery worker picks up task from queue
            ↓
        workerA.py executes: loads model, makes predictions
            ↓
        Result sent back to RabbitMQ
            ↓
        Flask retrieves result
            ↓
        HTML rendered and sent to browser
            ↓
        User sees predictions table
```

---

## Task 2: CloudInit + Docker

### Key Difference from Task 1

| Task 1 | Task 2 |
|--------|--------|
| Everything on 1 VM | Everything on 1 VM |
| Services run directly | Services run in containers |
| apt install rabbitmq-server | docker run rabbitmq:3.9 |
| Process management complex | Docker manages processes |
| Hard to scale horizontally | Easy to scale (more workers) |

### Architecture

Single VM with Docker:
- Docker Container Platform manages everything
- Container 1: RabbitMQ (port 5672)
- Container 2: Flask Web (port 5100)
- Container 3: Celery Worker
- All interconnected via Docker network

### CloudInit for Task 2

```yaml
#cloud-config

packages:
 - apt-transport-https
 - ca-certificates
 - curl
 - software-provides-common

runcmd:
 - echo "adding docker repo"
 - curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
 - add-apt-repository -y "deb [arch=amd64] https://download.docker.com/linux/ubuntu focal stable"
 - apt-get update -y
 - apt-get install -y docker-ce                    # Install Docker
 
 - git clone https://github.com/sztoor/model_serving.git
 
 # ← KEY DIFFERENCE: Instead of installing packages, use docker-compose
 - docker compose -f /model_serving/single_server_with_docker/production_server/docker-compose.yml up -d
```

### Docker Compose Configuration

```yaml
version: "3"
services:
  # Service 1: RabbitMQ Message Broker
  rabbit:
    hostname: rabbit
    image: rabbitmq:3.9-management          # Pre-built image
    environment:
      - RABBITMQ_DEFAULT_USER=rabbitmq
      - RABBITMQ_DEFAULT_PASS=rabbitmq
    ports:
      - "5672:5672"                          # AMQP protocol
      - "15672:15672"                        # Management UI
  
  # Service 2: Flask Web Application
  web:
    build:
      context: .                             # Build from current directory
      network: host
    restart: always
    ports:
      - "5100:5100"                          # Web server port
    depends_on:
      - rabbit                               # Wait for RabbitMQ first
  
  # Service 3: Celery Worker
  worker_1:
    build:
      context: .
      network: host
    hostname: worker_1
    entrypoint: celery                       # Run Celery instead of Flask
    command: -A workerA worker --loglevel=debug
    links:
      - rabbit                               # Connect to RabbitMQ
    depends_on:
      - rabbit
```

### Execution Steps

1. ✅ VM boots with CloudInit
2. ✅ Docker installed
3. ✅ `docker compose up -d` executed
4. ✅ Docker creates 3 containers in correct order (due to `depends_on`)
5. ✅ All services interconnected via Docker network

### Advantages over Task 1

- ✅ Easy to scale: `docker compose up --scale worker_1=3`
- ✅ Isolation: Each service has its own filesystem, processes
- ✅ Reproducibility: Same `docker-compose.yml` works everywhere

---

## Task 3: CloudInit + Ansible

### Evolution from Task 2 → Task 3

| Task 2 | Task 3 |
|--------|--------|
| 1 VM with all services | 2 VMs (Production + Development) |
| CloudInit does everything | CloudInit + Ansible orchestration |
| Manual scaling | Automatic, coordinated setup |
| Single point of failure | Separation of concerns |
| Hard to update config | Ansible playbooks for reproducibility |

### Why Multiple Servers?

```
Production Server:  Runs the application (users access this)
Development Server: For testing new models, CI/CD pipeline
```

### Code Walkthrough

#### Step 1: Create TWO VMs Simultaneously (`start_instances.py`)

```python
# Create PRODUCTION VM with prod-cloud-cfg.txt
userdata_prod = open('prod-cloud-cfg.txt')
instance_prod = nova.servers.create(
    name="arnab_prod_server_with_docker_" + str(identifier),
    image=image,
    flavor=flavor,
    userdata=userdata_prod,  # ← Different CloudInit script
    nics=nics
)

# Create DEVELOPMENT VM with dev-cloud-cfg.txt
userdata_dev = open('dev-cloud-cfg.txt')
instance_dev = nova.servers.create(
    name="arnab_dev_server_with_docker_" + str(identifier),
    image=image,
    flavor=flavor,
    userdata=userdata_dev,   # ← Different CloudInit script
    nics=nics
)

# Wait for BOTH to be ready
while inst_status_prod == 'BUILD' or inst_status_dev == 'BUILD':
    # Poll both VMs
    instance_prod = nova.servers.get(instance_prod.id)
    instance_dev = nova.servers.get(instance_dev.id)
    time.sleep(5)

# Extract IP addresses
ip_address_prod = instance_prod.networks[private_net][0]
ip_address_dev = instance_dev.networks[private_net][0]

print(f"Prod IP: {ip_address_prod}")
print(f"Dev IP: {ip_address_dev}")
```

**Key Differences from Task 1/2:**
- Creates 2 VMs, not 1
- Each has different CloudInit script
- Waits for BOTH to be ACTIVE
- Extracts IP addresses for next step (Ansible)

#### Step 2: CloudInit for Production (`prod-cloud-cfg.txt`)

```yaml
#cloud-config

users:
 - name: appuser                          # Create non-root user
   sudo: ALL=(ALL) NOPASSWD:ALL           # Allow sudo without password
   ssh_authorized_keys:
     - ssh-rsa AAAA...                    # ← Your SSH public key

byobu_default: system
```

#### Step 3: CloudInit for Development (`dev-cloud-cfg.txt`)

```yaml
#cloud-config
# Same as production - minimal setup
# Just creates appuser and SSH keys
# Ansible will do the real configuration
```

#### Step 4: Ansible Configuration (`setup_var.yml`)

```yaml
prod_home: /technical-training/model-serving/ci_cd/production_server
dev_home: /technical-training/model-serving/ci_cd/development_server
```

#### Step 5: Ansible Playbook (`configuration.yml`)

```yaml
- hosts: all                              # Run on ALL servers
  
  tasks:
   # COMMON TASKS for both servers
   - name: apt update
     apt: update_cache=yes upgrade=dist
     become: true                         # Run as root
   
   - name: Download git repository
     become: true
     git:
      repo: 'https://github.com/sztoor/model_serving.git'
      dest: /model_serving
   
   - name: Change ownership
     become: true
     file:
      path: /technical-training
      owner: appuser
      group: appuser

# PRODUCTION-SPECIFIC tasks
- hosts: prodserver                       # Only on production
  
  vars_files:
   - setup_var.yml
  
  tasks:
   - name: Install Docker dependencies
     apt: pkg={{item}} state=latest
     with_items:
      - apt-transport-https
      - ca-certificates
      - curl
      - software-provides-common
     become: true
   
   - name: Install Docker
     shell: |
       curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
       add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu focal stable"
       apt-get install docker-ce docker-compose
     become: true
   
   - name: Start production app with docker-compose
     shell: docker compose -f {{ prod_home }}/docker-compose.yml up -d
     become: true
```

### Ansible Hosts Configuration

On your client VM:
```bash
sudo nano /etc/ansible/hosts
```

Add:
```ini
[servers]
prodserver ansible_host=192.168.1.19
devserver ansible_host=192.168.1.17

[all:vars]
ansible_python_interpreter=/usr/bin/python3

[prodserver]
prodserver ansible_connection=ssh ansible_user=appuser

[devserver]
devserver ansible_connection=ssh ansible_user=appuser
```

### Execution Flow for Task 3

```
┌─────────────────────────────────────────────────────┐
│ 1. You run: python3 start_instances.py              │
└────────┬────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│ 2. Python creates 2 VMs on OpenStack simultaneously │
│    - Prod VM: 192.168.1.19                          │
│    - Dev VM: 192.168.1.17                           │
└────────┬────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│ 3. CloudInit runs on both (creates appuser + SSH)   │
└────────┬────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│ 4. Script outputs: IPs printed to console           │
│    Copy these IPs to /etc/ansible/hosts             │
└────────┬────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│ 5. Install Ansible on client VM:                    │
│    sudo apt install ansible                         │
└────────┬────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│ 6. Run Ansible playbook:                            │
│    ansible-playbook configuration.yml \             │
│      --private-key=/path/to/cluster-key             │
└────────┬────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│ 7. Ansible connects to BOTH VMs via SSH             │
│    Runs same tasks on both simultaneously           │
└────────┬────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│ 8. Common tasks executed (git clone, apt update)    │
└────────┬────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│ 9. Production-specific tasks (Docker + docker-comp) │
└────────┬────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│ 10. Both servers ready!                             │
│     - Prod: http://192.168.1.19:5100 (running app) │
│     - Dev: Ready for development                    │
└─────────────────────────────────────────────────────┘
```

---

## Task 4: Git Hooks CI/CD

### What Problem Does This Solve?

**Without Git Hooks:**
1. You improve the ML model on Dev server
2. Generate new `model.h5` and `model.json`
3. Manually copy to Production server
4. Manually restart services
5. Hope everything works ❌

**With Git Hooks:**
1. You improve ML model on Dev server
2. Generate new model files
3. `git add . && git commit && git push`
4. Automatically deployed to Production ✅
5. Zero manual steps

### Code Walkthrough

#### Step 1: SSH Key Setup (Enable passwordless deployment)

On Development VM:
```bash
# Generate SSH key (no password)
ssh-keygen -t rsa
# Output: /home/appuser/.ssh/id_rsa (private) + id_rsa.pub (public)
```

On Production VM:
```bash
# Add Dev's public key to authorized list
cat /home/appuser/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
# Now Dev can SSH to Prod without password
```

#### Step 2: Create Bare Git Repository (on Production)

```bash
# On Production VM, as appuser user
mkdir /home/appuser/my_project
cd /home/appuser/my_project
git init --bare
# Creates: hooks/, objects/, refs/ directories
```

**What is a "bare" repository?**
- Normal git repo: Has `.git/` folder + working directory
- Bare repo: Only contains what's in `.git/` (no working files)
- Used as a central repository for pushing (like GitHub)

#### Step 3: Create Git Hook Script (on Production)

File: `/home/appuser/my_project/hooks/post-receive`

```bash
#!/bin/bash
# This script runs AUTOMATICALLY after git push completes

while read oldrev newrev ref
do
  # Check if master branch was pushed
  if [[ $ref =~ .*/master$ ]]; then
    then
    echo "Master ref received. Deploying master branch to production..."
    
    # Checkout files to the actual application directory
    sudo git --work-tree=/model_serving/ci_cd/production_server \
             --git-dir=/home/appuser/my_project checkout -f
    
  else
    echo "Ref $ref received. Doing nothing: only master branch deploys."
  fi
done
```

**What does this script do?**
- Listens for incoming git pushes
- Checks if it's the `master` branch
- If yes: Extracts files from git repo to `/model_serving/ci_cd/production_server`
- If no: Ignores (safety measure)

Make it executable:
```bash
chmod +x /home/appuser/my_project/hooks/post-receive
```

#### Step 4: Configure Git on Development VM

```bash
# On Development VM
cd /home/appuser/my_project
git init                    # Initialize local repo

# Add production as remote
git remote add production appuser@192.168.1.19:/home/appuser/my_project
```

#### Step 5: Push Model to Production

On Development VM:
```bash
# Make changes to model
python3 /model_serving/ci_cd/development_server/neural_net.py

# Copy updated model files
cp /model_serving/ci_cd/development_server/model.* /home/appuser/my_project/

# Commit changes
cd /home/appuser/my_project/
git add .
git commit -m "new model"

# PUSH to production (triggers hook!)
git push production master
```

### What Happens on Push

```
┌─────────────────────────────────────────────────────┐
│ Development VM                                      │
│                                                     │
│ You run: git push production master                 │
└────────┬────────────────────────────────────────────┘
         │
         ▼ SSH connection to Production VM
┌─────────────────────────────────────────────────────┐
│ Production VM                                       │
│                                                     │
│ 1. Receives git push                               │
│ 2. Updates bare repo: /home/appuser/my_project    │
│ 3. Executes hook: post-receive script             │
└────────┬────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│ hook/post-receive runs:                            │
│                                                     │
│ git --work-tree=/model_serving/ci_cd/prod... \    │
│     --git-dir=/home/appuser/my_project \           │
│     checkout -f                                    │
│                                                     │
│ Extracts: model.h5, model.json to prod directory  │
└────────┬────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│ Production Server:                                  │
│                                                     │
│ /model_serving/ci_cd/production_server/            │
│   ├── model.h5 (UPDATED)                           │
│   ├── model.json (UPDATED)                         │
│   ├── app.py (uses new model)                      │
│   └── workerA.py (uses new model)                  │
│                                                     │
│ ✅ App automatically uses new model                │
│ ✅ No manual restart needed (containerized)        │
└─────────────────────────────────────────────────────┘
```

### Expected Output

```
Writing objects: 100% (4/4), 838 bytes | 838.00 KiB/s, done.
Total 4 (delta 2), reused 0 (delta 0), pack-reused 0
remote: Master ref received. Deploying master branch to production...
To 192.168.1.21:/home/appuser/my_project
c20d19e..666ca0c master -> master
```

---

## CloudInit vs Ansible

### Decision Tree: When to Use Each

**Question: How many VMs?**

- **1 VM**: Use CloudInit
  - Runs at VM boot
  - Perfect for single machine
  - Simple YAML syntax
  - Tasks 1 & 2

- **2+ VMs**: Use Ansible
  - Orchestrates multiple servers
  - Run same tasks on all
  - Consistent configuration
  - Tasks 3 & 4

- **Scale & Reproducibility**: Use Both
  - CloudInit: Initial setup
  - Ansible: Complex config
  - Minimal CloudInit
  - Powerful Ansible playbooks

### Detailed Comparison

| Feature | CloudInit | Ansible |
|---------|-----------|---------|
| **When Runs** | At VM boot (one-time) | After VM is running (anytime) |
| **How Triggered** | Automatically by OpenStack | Manually or via script |
| **Best For** | Initial machine setup | Configuration management |
| **Multiple VMs** | Each gets separate script | Coordinates all servers |
| **Idempotency** | ❌ Runs every boot | ✅ Safe to run multiple times |
| **Error Recovery** | ❌ Restart VM to retry | ✅ Modify & rerun playbook |
| **Dependencies** | Hard to manage | ✅ Easy with `depends_on` |
| **Language** | YAML (cloud-config) | YAML (playbooks) |
| **SSH Access** | Need key in CloudInit | Connects via SSH |
| **Use Case** | Quick one-time setup | Scalable deployments |

### Real-World Analogy

**CloudInit** = Building contractor's initial blueprints
- Applied once when building starts
- Hard to change mid-construction

**Ansible** = Building supervisor's checklist
- Can run anytime to verify everything
- Easy to adjust and reapply

---

## Master Summary

### Assignment 3: Complete Learning Path

```
🚀 Your Journey
   ↓
Phase 1: Learn CloudInit
   ↓
Task 1: CloudInit Only
   ├─ Single VM
   ├─ No Docker
   └─ Key: Understand Flask + Celery + RabbitMQ
   ↓
Phase 2: Add Containerization
   ↓
Task 2: CloudInit + Docker
   ├─ Single VM
   ├─ 3 Containers
   └─ Key: Understand Docker isolation + Scaling
   ↓
Phase 3: Scale Horizontally
   ↓
Task 3: CloudInit + Ansible
   ├─ 2 VMs (Prod + Dev)
   ├─ Orchestrated setup
   └─ Key: Understand Multi-server orchestration
   ↓
Phase 4: Continuous Deployment
   ↓
Task 4: Git Hooks CI/CD
   ├─ Auto-deploy model.h5
   ├─ git push → automatic deployment
   └─ Key: Understand CI/CD Pipeline
   ↓
✅ Master Production-Ready System
```

---

## Quick Reference

### Task Comparison Table

| Aspect | Task 1 | Task 2 | Task 3 | Task 4 |
|--------|--------|--------|--------|--------|
| **VMs Created** | 1 | 1 | 2 | Uses Task 3 VMs |
| **Deployment Tool** | CloudInit | CloudInit | CloudInit + Ansible | Git Hooks |
| **Services Location** | Directly on VM | Docker containers | Docker containers | Git-based |
| **Flask/Celery/RabbitMQ** | Direct install | Container images | Container images | From git repo |
| **Scalability** | Can't scale | Easy horizontal | Coordinated | Auto-deployment |
| **Configuration** | Fixed | Fixed | Reproducible | Dynamic |
| **Model Updates** | Manual copy | Manual copy | Manual copy | `git push` ✅ |
| **Production URL** | VM:5100 | VM:5100 | Prod-VM:5100 | Prod-VM:5100 |
| **Learning Focus** | IaC + CloudInit | Docker + Orchestration | Ansible + Multi-server | CI/CD Pipeline |

### Execution Commands Summary

#### Task 1: CloudInit Only
```bash
cd /model_serving/openstack-client/single_node_without_docker_client/
python3 start_instance.py
# Wait 10-15 minutes
# Access: http://PROD-VM-IP:5100/predictions
```

#### Task 2: CloudInit + Docker
```bash
cd /model_serving/openstack-client/single_node_with_docker_client/
python3 start_instance.py
# Wait 10-15 minutes
# Access: http://PROD-VM-IP:5100/predictions
```

#### Task 3: CloudInit + Ansible
```bash
cd /model_serving/openstack-client/single_node_with_docker_ansible_client/

# Step 1: Create VMs
python3 start_instances.py
# Captures: PROD-IP and DEV-IP

# Step 2: Configure Ansible
sudo nano /etc/ansible/hosts
# Add prod and dev server IPs

# Step 3: Run Ansible playbook
export ANSIBLE_HOST_KEY_CHECKING=False
ansible-playbook configuration.yml \
  --private-key=/home/ubuntu/cluster-keys/cluster-key

# Wait 10-15 minutes
# Access Prod: http://PROD-IP:5100/predictions
```

#### Task 4: Git Hooks CI/CD
```bash
# On Production VM (from Task 3)
mkdir /home/appuser/my_project
cd /home/appuser/my_project
git init --bare
# Create hooks/post-receive script with chmod +x

# On Development VM
mkdir /home/appuser/my_project
cd /home/appuser/my_project
git init
git remote add production appuser@PROD-IP:/home/appuser/my_project

# Copy model files, commit, and push
cp /model_serving/ci_cd/development_server/model.* .
git add .
git commit -m "new model"
git push production master

# ✅ Automatically deployed!
# Access: http://PROD-IP:5100/predictions (uses new model)
```

### Key Concepts Summary

#### CloudInit
- 🟢 **Runs**: At VM boot time
- 🟢 **Use Case**: Initial machine setup
- 🟢 **Format**: YAML `#cloud-config`
- 🟢 **Trigger**: OpenStack passes via `userdata=`

#### Docker & Docker Compose
- 🔵 **Containers**: Isolated applications
- 🔵 **docker-compose.yml**: Define 3+ services
- 🔵 **Benefit**: Easy scaling, resource isolation
- 🔵 **Command**: `docker compose up --scale worker_1=3`

#### Ansible
- 🟣 **Hosts**: Works on multiple servers
- 🟣 **Playbooks**: YAML configuration files
- 🟣 **Idempotent**: Safe to run multiple times
- 🟣 **Connection**: SSH-based remote execution

#### Git Hooks
- 🟠 **Trigger**: On git push/commit
- 🟠 **post-receive**: Runs AFTER push received
- 🟠 **Benefit**: Automated deployments
- 🟠 **Security**: Only master branch deploys

---

## Architecture Progression

```
Task 1                    Task 2                    Task 3                    Task 4
━━━━━━━                   ━━━━━━━                   ━━━━━━━                   ━━━━━━━

┌─────────┐              ┌─────────┐              ┌──────────┐              ┌──────────┐
│ 1 VM    │              │ 1 VM    │              │ 2 VMs    │              │ 2 VMs    │
│ Ubuntu  │              │ Ubuntu  │              │ Prod+Dev │              │ Prod+Dev │
└─────────┘              └────┬────┘              └────┬─────┘              └────┬─────┘
     │                        │                       │                         │
     ├─ Flask ─┐         ┌────┴──────┬────────┐      │                         │
     ├─ RabbitMQ        │           │        │      │                         │
     └─ Celery      ┌────▼────┐ ┌───▼────┐ ┌─▼────┐ │                         │
                    │RabbitMQ │ │ Flask  │ │Worker│ │                         │
                    └─────────┘ └────────┘ └──────┘ │                         │
                    (Containers)                      │                         │
                                                      │                         │
                    CloudInit             CloudInit + Ansible        CloudInit + Ansible
                       ✓                  + Docker Compose           + Ansible + Git Hooks
                                                      │                         │
                                            ┌─────────┴────────┐      ┌─────────┴────────┐
                                            │                  │      │                  │
                                        ┌───▼────┐        ┌───▼────┐ ┌──▼────┐      ┌──▼────┐
                                        │ Prod   │        │ Dev    │ │ Prod  │      │ Dev  │
                                        │ App    │        │ Dev    │ │ App   │      │ Dev  │
                                        └────────┘        └────────┘ └───────┘      └──────┘
                                        
                                                                    Auto-deploy via
                                                                    git push master
                                                                         ↓
                                                                    Prod updated!
```

---

## Final Checklist: What You Now Understand

✅ **How OpenStack APIs work** - `nova.servers.create()`
✅ **CloudInit automation** - Runs scripts at VM boot
✅ **Docker containerization** - Isolated services
✅ **docker-compose** - Define multi-container apps
✅ **Ansible orchestration** - Configure multiple servers
✅ **Git hooks** - Automated CI/CD deployments
✅ **SSH key management** - Passwordless authentication
✅ **Multi-server architecture** - Dev + Prod separation
✅ **Message queues** - RabbitMQ for async tasks
✅ **Infrastructure as Code (IaC)** - Entire stack automated

---

## Document Information

- **Created**: May 6, 2026
- **Subject**: Assignment 3 - Complete Deployment Guide
- **Scope**: Tasks 1-4, Technologies: CloudInit, Docker, Ansible, Git Hooks
- **Purpose**: Comprehensive reference for infrastructure automation and CI/CD concepts
