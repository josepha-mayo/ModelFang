"""
ModelFang API Server

Backend API for the Next.js Dashboard.
"""

import os
import json
import threading
import uuid
import time
from pathlib import Path
from flask import Flask, jsonify, request
from flask_cors import CORS

from modelfang.api import run_attack
from modelfang.config.loader import load_models_config

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

from modelfang.compliance.owasp import ComplianceMapper

# Simple in-memory job store (replace with Redis/DB in production)
JOBS = {}
print(f"DEBUG: API Server initialized. JOBS dict is at {id(JOBS)}")

@app.route("/")
def index():
    return jsonify({
        "status": "online",
        "message": f"ModelFang Backend API. Frontend: {os.environ.get('FRONTEND_URL', 'Not configured')}",
        "endpoints": ["/api/models", "/api/attack", "/api/health", "/api/risk"]
    })

@app.route("/api/risk")
def risk_assessment():
    """Get aggregate risk assessment from output folder."""
    successful_categories = []
    findings = []
    
    output_dir = Path("output")
    
    # Read all attack files from output folder
    if output_dir.exists():
        for file_path in output_dir.glob("attack_*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                    # Check if attack was successful
                    if data.get("success", False):
                        category = data.get("category", "jailbreak")
                        max_score = data.get("evaluation_summary", {}).get("max_score", 0)
                        
                        # Map to risk categories
                        if category in ["jailbreak", "prompt_injection"]:
                            successful_categories.append("jailbreak")
                        if category in ["injection", "code_injection"]:
                            successful_categories.append("injection")
                        if category in ["exfiltration", "data_leak"]:
                            successful_categories.append("exfiltration")
                        
                        # Also add the raw category
                        if category not in successful_categories:
                            successful_categories.append(category)
                        
                        # Collect findings from transcript
                        transcript = data.get("conversation_transcript", [])
                        for i, msg in enumerate(transcript):
                            if msg.get("role") == "user":
                                findings.append({
                                    "type": category,
                                    "severity": "High" if max_score > 0.8 else "Medium",
                                    "prompt": msg.get("content", "")[:100] + "...",
                                    "status": "Vulnerable"
                                })
                                break  # Only first prompt
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                continue
    
    # Also include in-memory jobs
    for job in JOBS.values():
        if job["status"] == "completed" and job.get("result"):
            result = job["result"]
            success_score = result.get("success_score", 0.0)
            
            if success_score > 0.6:
                attack_id = job.get("attack_id", "")
                if "jailbreak" in attack_id or "attacker" in attack_id:
                    successful_categories.append("jailbreak")
                elif "injection" in attack_id:
                    successful_categories.append("injection")
    
    # Remove duplicates
    successful_categories = list(set(successful_categories))
    
    assessment = ComplianceMapper.analyze_risk(successful_categories)
    assessment["findings"] = findings
    return jsonify(assessment)

@app.route("/api/history")
def attack_history():
    """List past attack results from output folder."""
    output_dir = Path("output")
    if not output_dir.exists():
        return jsonify({"attacks": []})
    
    attacks = []
    for file_path in sorted(output_dir.glob("attack_*.json"), reverse=True):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                attacks.append({
                    "id": data.get("attack_id", file_path.stem),
                    "name": data.get("attack_name", "Unknown"),
                    "status": data.get("status", "unknown"),
                    "success": data.get("success", False),
                    "turns": data.get("turns_to_success", -1),
                    "max_score": data.get("evaluation_summary", {}).get("max_score", 0),
                    "timestamp": data.get("timestamp", ""),
                    "category": data.get("category", "unknown"),
                    "filename": file_path.name
                })
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            continue
    
    return jsonify({"attacks": attacks})

@app.route("/api/history/<filename>")
def get_attack_detail(filename):
    """Get full attack detail by filename."""
    file_path = Path("output") / filename
    if not file_path.exists():
        return jsonify({"error": "Attack not found"}), 404
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "version": "0.4.0"})

@app.route("/api/models", methods=['GET', 'POST'])
def handle_models():
    """List available target models."""
    if request.method == 'GET':
    try:
        models_conf = load_models_config()
        targets = [
            {
                "id": m.model_id, 
                "name": m.model_name, 
                "provider": m.provider,
                "role": m.role
            } 
            for m in models_conf.get_targets()
        ] + _in_memory_models
        if request.method == 'POST':
            if not request.is_json:
                return jsonify({"error": "Missing JSON in request"}), 400
            data = request.get_json()
            if 'model_id' not in data or 'model_name' not in data or 'provider' not in data:
                return jsonify({"error": "Model details are required"}), 400
            _in_memory_models.append({
                "id": data['model_id'],
                "name": data['model_name'],
                "provider": data['provider']
            })
            return jsonify({"message": "Model added successfully"}), 201
        return jsonify({"targets": targets})
            return jsonify({"targets": targets})
    elif request.method == 'POST':
        if not request.is_json:
            return jsonify({'error': 'Invalid request, JSON expected'}), 400
        data = request.get_json()
        if 'model_id' not in data or 'model_name' not in data or 'provider' not in data:
            return jsonify({'error': 'Model ID, name, and provider are required'}), 400
        model_id = data['model_id']
        model_name = data['model_name']
        provider = data['provider']
        _in_memory_models.append({'id': model_id, 'name': model_name, 'provider': provider})
        return jsonify({'message': 'Model created successfully'}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/goals")
def list_goals():
    """List available attack goals from dataset."""
    try:
        goals_path = Path("modelfang/datasets/attack_goals.json")
        if not goals_path.exists():
             return jsonify({"goals": []})
        
        with open(goals_path, "r", encoding="utf-8") as f:
            goals = json.load(f)
            
        # Ensure it's a list (handle migration script artifact if it wrapped it)
        if isinstance(goals, dict) and "goals" in goals:
            goals = goals["goals"]
            
        return jsonify({"goals": goals})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/attack", methods=["POST"])
def start_attack():
    """Start an attack execution."""
    data = request.json
    attack_id = data.get("attack_id", "template:standard")
    model_id = data.get("model_id")
    attacker_model_id = data.get("attacker_model_id") # New field
    context = data.get("context", {})
    seed = data.get("seed")
    
    if not model_id:
        return jsonify({"error": "model_id is required"}), 400
        
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "id": job_id,
        "attack_id": attack_id,  # Store for risk tracking
        "model_id": model_id,    # Store for reporting
        "status": "pending",
        "result": None,
        "created_at": time.time()
    }
    
    def _run():
        try:
            JOBS[job_id]["status"] = "running"
            result = run_attack(
                attack_id=attack_id,
                target_model_id=model_id,
                context=context,
                seed=seed,
                config_dir=os.environ.get("MODELFANG_CONFIG_DIR"),
                data=data
            )
            JOBS[job_id]["status"] = "completed"
            JOBS[job_id]["result"] = result
        except Exception as e:
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["error"] = str(e)
            
    thread = threading.Thread(target=_run)
    thread.start()
    
    return jsonify({"job_id": job_id, "status": "pending"})

@app.route("/api/jobs/<job_id>")
def get_job(job_id):
    """Get job status and result."""
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)

def start_server(port=5000, debug=True):
    app.run(host="0.0.0.0", port=port, debug=debug)

if __name__ == "__main__":
    start_server()
