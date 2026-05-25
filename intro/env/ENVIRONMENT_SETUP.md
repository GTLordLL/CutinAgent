# CutinAgent Environment Setup Guide

This document covers the complete process of deploying CutinAgent from scratch, including system dependencies, Docker + Ollama configuration, model customization, and parameter tuning. Also useful as a self-check checklist for already-configured environments.

---

## Requirements

| Component | Requirement |
|-----------|-------------|
| OS | Ubuntu 24.04 LTS (x86_64) |
| GPU | NVIDIA RTX 3060 6GB (or equivalent VRAM) |
| Docker | Docker Engine + Docker Compose v2 |
| NVIDIA | NVIDIA Driver + NVIDIA Container Toolkit |
| Python | 3.10+ |

---

## 1. Installing System Dependencies

The following assumes a fresh Ubuntu 24.04 installation. Skip steps that are already done.

### 1.1 NVIDIA Driver

Most Ubuntu 24.04 installations include the driver. Check first:

```bash
nvidia-smi
```

If the command runs and shows GPU info (e.g., `NVIDIA GeForce RTX 3060 ...`), you're good — skip to the next step.

If you get `command not found`:

```bash
sudo apt update
sudo apt install nvidia-driver-550 -y
sudo reboot
# Verify after reboot
nvidia-smi
```

### 1.2 Docker

```bash
# Official install script
curl -fsSL https://get.docker.com | sudo bash

# Add your user to the docker group to avoid using sudo for every command
sudo usermod -aG docker $USER
```

> **Important**: After `usermod -aG docker`, you must **log out and back in** (or run `newgrp docker`) for the change to take effect. Verify with `docker ps` — no permission error means success.

### 1.3 Docker Compose Plugin

```bash
sudo apt install docker-compose-plugin -y
docker compose version   # Verify
```

### 1.4 NVIDIA Container Toolkit

> **This is the #1 pitfall.** Without it, Docker containers cannot see the GPU, and Ollama will fall back to pure CPU inference — a 4B model will crawl at ~1 token/s, effectively unusable.

```bash
# Add NVIDIA's official repository
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update
sudo apt install nvidia-container-toolkit -y

# Restart Docker to apply
sudo systemctl restart docker

# Verify: can Docker see the GPU?
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
```

If the last command prints GPU information, the toolkit is working.

#### Network Issues (Users in China)

The `curl` / `apt` / `docker pull` commands above may fail due to network restrictions. If you encounter timeouts or `Connection refused`:

- **Docker mirror**: Edit `/etc/docker/daemon.json` to add a local mirror (e.g., Alibaba Cloud, USTC), then `sudo systemctl restart docker`
- **apt mirror**: Replace `/etc/apt/sources.list` with a Tsinghua or Alibaba Cloud mirror
- **Ollama model pull**: Model downloads go through Ollama's official registry; use a proxy or wait if the connection is slow

> Mirror addresses change over time. Search for "Ubuntu 24.04 apt mirror" or "Docker mirror China" for current configuration.

---

## 2. Deploying the Project

### One-Click Setup (Recommended)

Once system dependencies are installed, let the automation script handle the rest:

```bash
git clone https://github.com/GTLordLL/CutinAgent.git
cd CutinAgent
bash setup.sh
```

`setup.sh` automates: environment self-check → Ollama container startup → base model pull → custom model creation → Python virtual environment setup. Fully idempotent — skips completed steps and cleans up intermediate artifacts on failure.

### Manual Setup

#### 2.1 Start the Ollama Container

The project includes a `docker-compose.yml`:

```bash
docker compose up -d
curl http://localhost:11434/api/tags   # Verify
```

#### 2.2 Pull the Model and Create a Custom Version

This project uses long prompts (full SOP plan + multi-round history). The default 2K context window is insufficient — we extend it to 8K:

```bash
# Pull the base model (Q4_K_M quantization, ~2.5 GB)
docker exec cutin-ollama ollama pull qwen3:4b-instruct

# Create the custom model
docker exec cutin-ollama ollama create qwen3:4b-instruct_8k -f - << 'MODELFILE'
FROM qwen3:4b-instruct
TEMPLATE "{{ .Prompt }}"
PARAMETER num_ctx 8192
PARAMETER num_gpu 40
PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"
MODELFILE

# Verify
docker exec cutin-ollama ollama list | grep qwen3:4b-instruct_8k
```

See **Model Parameter Tuning** below for details on each parameter.

#### 2.3 Install Python Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> **Remote Ollama**: If Ollama runs on a different machine, set `export OLLAMA_BASE_URL=http://<your-host>:11434`.

---

## 3. Model Parameter Tuning

The custom model `qwen3:4b-instruct_8k` has two key parameters that you should adjust for your hardware:

### `num_gpu` — GPU Layer Count

Controls how many model layers are offloaded to the GPU. **Higher = faster inference, but more VRAM usage.**

- qwen3 4B has ~36 layers; setting **40** (default) ensures all layers run on GPU
- Tested on RTX 3060 6GB: all layers on GPU use only ~4.2 GB VRAM, achieving **~45 tokens/s**
- If your GPU has less VRAM (e.g., 4 GB), reduce this value to let some layers fall back to CPU (slower, but functional)
- If your GPU has more VRAM (e.g., 12 GB+), keep it at 40 or higher

Check actual VRAM usage:

```bash
docker exec cutin-ollama nvidia-smi
```

### `num_ctx` — Context Window

Controls how many tokens the model can "see" at once. **Larger = longer conversations and prompts, but higher VRAM usage.**

- Set to **8192** (default) to accommodate the full SOP plan + multi-round history
- Can be adjusted to 4096 (save VRAM) or 16384 (more history), depending on your needs
- Note: doubling the context window ≈ significantly higher VRAM consumption

### How to Adjust

Modify the parameter values in the Modelfile and recreate the model:

```bash
docker exec cutin-ollama ollama create qwen3:4b-instruct_8k -f - << 'MODELFILE'
FROM qwen3:4b-instruct
TEMPLATE "{{ .Prompt }}"
PARAMETER num_ctx 8192
PARAMETER num_gpu 40
PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"
MODELFILE
```

Recreating overwrites the existing model — no need to delete the old one first.

---

## 4. Running

```bash
source .venv/bin/activate
python main.py
```

Modify `ACTIVE_CASE` at the top of `main.py` to switch test scenarios. Example instructions:

- `Check the running status of the docker service`
- `I suspect /var/log is taking up too much disk space`
- `Run a comprehensive system health check`

---

## 5. Uninstalling

```bash
# Stop and remove the Ollama container (keeps model data volume)
docker compose down

# Stop and remove container + model data volume (full cleanup)
docker compose down -v
```
