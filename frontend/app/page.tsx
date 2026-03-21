"use client";

export const dynamic = 'force-dynamic';

import React, { useState, useEffect, useRef } from 'react';
import { Terminal, Play, ShieldAlert, Cpu, Activity, Lock, RefreshCw } from "lucide-react";
import { motion } from "framer-motion";
import Link from 'next/link';

// Types
interface Model {
  id: string;
  name: string;
  provider: string;
  role: string;
}

interface LogEntry {
  timestamp: string;
  message: string;
  type: 'info' | 'error' | 'success';
  data?: any;
}

interface AttackGoal {
  id: string;
  name: string;
  category: string;
  goal: string;
}

export default function Dashboard() {
  const [models, setModels] = useState<Model[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [selectedAttack, setSelectedAttack] = useState("template:standard");
  const [selectedAttacker, setSelectedAttacker] = useState("attacker-gemini");
  const [selectedDataset, setSelectedDataset] = useState("jb_dan_11");
  const [selectedPlugins, setSelectedPlugins] = useState<string[]>(["jailbreak"]);
  const [attackGoals, setAttackGoals] = useState<AttackGoal[]>([]);
  const [selectedAttackGoal, setSelectedAttackGoal] = useState("");
  const [attackMode, setAttackMode] = useState<"template" | "attacker" | "dataset" | "systematic">("template");
  const [isRunning, setIsRunning] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [status, setStatus] = useState("IDLE");
  const [score, setScore] = useState<number | null>(null);

  const [selectedLog, setSelectedLog] = useState<any>(null); // For modal

  const logsEndRef = useRef<HTMLDivElement>(null);

  // Fetch models and goals on load
  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000'}/api/models`)
      .then(res => res.json())
      .then(data => {
if (data.targets) { setModels(data.targets); if (data.targets.length > 0) setSelectedModel(data.targets[0].id); }
      })
      .catch(err => addLog(`Failed to load models: ${err}`, 'error'));

    fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000'}/api/goals`)
      .then(res => res.json())
      .then(data => {
        if (data.goals) {
           setAttackGoals(data.goals);
           if (data.goals.length > 0) setSelectedAttackGoal(data.goals[0].id);
        }
      })
      .catch(err => addLog(`Failed to load goals: ${err}`, 'error'));
      
    addLog("System initialized. Ready for Red Teaming.", 'info');
  }, []);

  // Helper to group goals by category
  const categories = Array.from(new Set(attackGoals.map(g => g.category))).sort();

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const addLog = (msg: string, type: 'info'|'error'|'success' = 'info', data: any = null) => {
    setLogs(prev => [...prev, {
      timestamp: new Date().toLocaleTimeString(),
      message: msg,
      type,
      data // Store full step result here
    }]);
  };

  const handleRun = async () => {
    if (!selectedModel) {
      addLog("Select a target model first.", 'error');
      return;
    }

    setIsRunning(true);
    setStatus("RUNNING");
    setScore(null);
    setLogs([]); 
    
    let finalAttackId = selectedAttack;
    let context = { 
        source: "dashboard",
        goal: selectedAttackGoal // Pass selected goal to backend
    };
    
    if (attackMode === "attacker") {
        finalAttackId = `attacker:auto`;
        addLog(`Initiating Red Team Attack: ${selectedAttacker} vs ${selectedModel}...`, 'info');
    } else if (attackMode === "dataset") {
        finalAttackId = `dataset:${selectedDataset}`;
        addLog(`Loading Dataset Attack: ${selectedDataset} -> ${selectedModel}...`, 'info');
    } else if (attackMode === "systematic") {
        if (selectedPlugins.length === 0) {
            addLog("Select at least one plugin.", 'error');
            setIsRunning(false);
            return;
        }
        finalAttackId = `systematic:${selectedPlugins.join(",")}`;
        addLog(`Initiating Systematic Probe: [${selectedPlugins.join(", ")}] -> ${selectedModel}...`, 'info');
    } else {
        // Handle Advanced Techniques that need dynamic goal injection
        // If selectedAttack contains ':auto', replace it with the actual goal
        if (finalAttackId.includes(":auto")) {
             finalAttackId = finalAttackId.replace(":auto", `:${selectedAttackGoal}`);
        }
        addLog(`Initiating attack: ${finalAttackId} -> ${selectedModel}...`, 'info');
    }

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000'}/api/attack`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
           model_id: selectedModel,
           attack_id: finalAttackId,
           attacker_model_id: selectedAttacker,
           context: context
        })
      });

      const data = await res.json();
      const jobId = data.job_id;
      
      addLog(`Job started: ${jobId} (ID: ${finalAttackId})`, 'info');

      // Poll for status
      const interval = setInterval(async () => {
        try {
          const check = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000'}/api/jobs/${jobId}`);
          const jobData = await check.json();
          
          if (jobData.status === 'completed' || jobData.status === 'failed') {
            clearInterval(interval);
            setIsRunning(false);
            setStatus(jobData.status.toUpperCase());
            
            if (jobData.status === 'completed') {
              const result = jobData.result;
              setScore(result.success_score);
              addLog(`Execution completed. Score: ${result.success_score.toFixed(2)}`, 'success', result);
              result.step_results?.forEach((step: any) => {
                 addLog(`[STEP ${step.step_id}] ${step.success ? 'PASSED (VULNERABLE)' : 'RESISTED'} - ${step.evaluation?.reasoning || 'No Eval'}`, step.success ? 'success' : 'error', step);
              });
            } else {
               addLog(`Attack failed: ${jobData.error}`, 'error');
            }
          }
        } catch (err) {
          console.error("Polling error:", err);
        }
      }, 1000);

    } catch (err) {
      addLog(`API Connection Error: ${err}`, 'error');
      setIsRunning(false);
      setStatus("ERROR");
    }
  };

  return (
    <div className="min-h-screen bg-black text-white p-6 grid grid-cols-1 lg:grid-cols-4 gap-6 font-mono">
      {selectedLog && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-6" onClick={() => setSelectedLog(null)}>
            <div className="bg-gray-900 border border-gray-700 p-6 rounded-lg max-w-3xl w-full max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
                <h3 className="text-xl font-bold mb-4 text-red-500">Step Detail Viewer</h3>
                <div className="space-y-4">
                    <div>
                        <span className="text-xs text-gray-500 uppercase tracking-wider">Attacker Prompt</span>
                        <div className="bg-black p-3 rounded border border-gray-800 text-sm whitespace-pre-wrap font-mono mt-1 text-gray-300">
                            {selectedLog.prompt || "No prompt data"}
                        </div>
                    </div>
                    <div>
                        <span className="text-xs text-gray-500 uppercase tracking-wider">Target Response</span>
                        <div className={`p-3 rounded border text-sm whitespace-pre-wrap font-mono mt-1 ${selectedLog.success ? 'bg-red-900/20 border-red-900 text-red-200' : 'bg-black border-gray-800 text-gray-300'}`}>
                            {selectedLog.response || "No response data"}
                        </div>
                    </div>
                     <div>
                        <span className="text-xs text-gray-500 uppercase tracking-wider">Evaluation</span>
                        <div className="bg-black p-3 rounded border border-gray-800 text-sm font-mono mt-1 text-gray-400">
                            {JSON.stringify(selectedLog.evaluation || {}, null, 2)}
                        </div>
                    </div>
                </div>
                <button onClick={() => setSelectedLog(null)} className="mt-6 w-full py-2 bg-gray-800 hover:bg-gray-700 rounded text-sm font-bold">CLOSE</button>
            </div>
        </div>
      )}
    
      {/* Sidebar */}
      <div className="lg:col-span-1 border-r border-gray-800 pr-6">
        <header className="mb-8 flex items-center space-x-3">
            <img src="/logo.png" alt="Logo" className="w-12 h-12" />
            <div>
                 <h1 className="text-2xl font-bold tracking-tighter text-red-500">MODELFANG</h1>
                 <p className="text-xs text-gray-500">v0.4.0 ANALYST DASHBOARD</p>
            </div>
        </header>
        
        <div className="space-y-6">
            <div className="bg-gray-900 p-4 rounded border border-gray-800">
                <h3 className="text-sm text-gray-400 mb-2 flex items-center"><Cpu size={16} className="mr-2"/> Target Model (Victim)</h3>
                <select 
                    className="w-full bg-black border border-gray-700 p-2 rounded text-sm focus:border-red-500 outline-none"
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                    disabled={isRunning}
                >
                    <option value="">Select Target...</option>
                    {models.filter(m => m.role === 'target').map(m => (
                        <option key={m.id} value={m.id}>{m.name}</option>
                    ))}
                    {models.length === 0 && <option value="target-llama3">Llama 3 (Target)</option>}
                </select>
            </div>
            
            <div className="bg-gray-900 p-4 rounded border border-gray-800">
                <h3 className="text-sm text-gray-400 mb-2 flex items-center"><ShieldAlert size={16} className="mr-2"/> Attack Mode</h3>
                <div className="flex space-x-1 mb-3">
                    <button onClick={() => setAttackMode("template")} className={`flex-1 text-[10px] py-1 rounded ${attackMode==="template" ? "bg-red-600" : "bg-gray-800"}`}>Template</button>
                    <button onClick={() => setAttackMode("attacker")} className={`flex-1 text-[10px] py-1 rounded ${attackMode==="attacker" ? "bg-red-600" : "bg-gray-800"}`}>Auto-LLM</button>
                    <button onClick={() => setAttackMode("dataset")} className={`flex-1 text-[10px] py-1 rounded ${attackMode==="dataset" ? "bg-red-600" : "bg-gray-800"}`}>Dataset</button>
                    <button onClick={() => setAttackMode("systematic")} className={`flex-1 text-[10px] py-1 rounded ${attackMode==="systematic" ? "bg-red-600" : "bg-gray-800"}`}>Systematic</button>
                </div>

                {attackMode === "template" && (
                    <>
                    <select 
                        className="w-full bg-black border border-gray-700 p-2 rounded text-sm focus:border-red-500 outline-none"
                        value={selectedAttack}
                        onChange={(e) => setSelectedAttack(e.target.value)}
                        disabled={isRunning}
                    >
                        <option value="template:standard">Standard 6-Layer Jailbreak</option>
                        <option value="template:roles">Roleplay Escalation</option>
                        <option value="template:logic">Logical Paradox</option>
                        <optgroup label="Advanced Techniques (Phase 9)">
                            <option value="iris:auto">IRIS (Self-Jailbreak)</option>
                            <option value="puppetry:auto">Policy Puppetry (Framing)</option>
                            <option value="gcg:auto">AmpleGCG (Transfer Suffix)</option>
                            <option value="weak-strong:auto">Weak-to-Strong (Logprob)</option>
                        </optgroup>
                    </select>

                    <div className="space-y-2 mt-3">
                        <label className="text-xs text-gray-500">Target Goal / Payload</label>
                        <select 
                            className="w-full bg-black border border-gray-700 p-2 rounded text-sm focus:border-red-500 outline-none"
                            value={selectedAttackGoal}
                            onChange={(e) => setSelectedAttackGoal(e.target.value)}
                            disabled={isRunning}
                        >
                            <option value="bypass_safety">General Safety Bypass</option>
                            {categories.map(cat => (
                                <optgroup key={cat} label={cat}>
                                    {attackGoals.filter(g => g.category === cat).map(g => (
                                        <option key={g.id} value={g.id}>{g.name}</option>
                                    ))}
                                </optgroup>
                            ))}
                        </select>
                    </div>
                    </>
                )}

                {attackMode === "attacker" && (
                    <>
                     <div className="space-y-2">
                        <label className="text-xs text-gray-500">Attacker Model (Red Team)</label>
                        <select 
                            className="w-full bg-black border border-gray-700 p-2 rounded text-sm focus:border-red-500 outline-none"
                            value={selectedAttacker}
                            onChange={(e) => setSelectedAttacker(e.target.value)}
                            disabled={isRunning}
                        >
                            <option value="attacker-gemini">Gemini flash (Attacker)</option>
                            <option value="attacker-llama3">Llama 3 (Attacker)</option>
                        </select>
                     </div>

                     <div className="space-y-2 mt-3">
                        <label className="text-xs text-gray-500">Attack Goal / Type</label>
                        <select 
                            className="w-full bg-black border border-gray-700 p-2 rounded text-sm focus:border-red-500 outline-none"
                            value={selectedAttackGoal}
                            onChange={(e) => setSelectedAttackGoal(e.target.value)}
                            disabled={isRunning}
                        >
                            <option value="bypass_safety">General Safety Bypass</option>
                            {categories.map(cat => (
                                <optgroup key={cat} label={cat}>
                                    {attackGoals.filter(g => g.category === cat).map(g => (
                                        <option key={g.id} value={g.id}>{g.name}</option>
                                    ))}
                                </optgroup>
                            ))}
                        </select>
                     </div>
                    </>
                )}
                
            {attackMode === "dataset" && (
                     <div className="space-y-2">
                        <label className="text-xs text-gray-500">Static Prompt</label>
                        <select 
                            className="w-full bg-black border border-gray-700 p-2 rounded text-sm focus:border-red-500 outline-none"
                            value={selectedDataset}
                            onChange={(e) => setSelectedDataset(e.target.value)}
                            disabled={isRunning}
                        >
                            <option value="jb_dan_11">DAN 11.0</option>
                            <option value="jb_dev_mode">Developer Mode</option>
                            <option value="jb_grandma">Deceased Grandma</option>
                            <option value="jb_payload_split">Payload Splitting</option>
                            <option value="random">Random from Dataset</option>
                        </select>
                     </div>
                )}

                {attackMode === "systematic" && (
                     <div className="space-y-2">
                        <label className="text-xs text-gray-500">Select a Plugin </label>
                        <div className="grid grid-cols-2 gap-2">
                             {["jailbreak", "injection", "hallucination", "social", "component", "emotional", "crescendo"].map(plugin => (
                                 <label key={plugin} className="flex items-center space-x-2 text-xs bg-black border border-gray-800 p-2 rounded cursor-pointer hover:border-red-500">
                                     <input 
                                         type="checkbox" 
                                         checked={selectedPlugins.includes(plugin)}
                                         onChange={(e) => {
                                             if (e.target.checked) setSelectedPlugins([...selectedPlugins, plugin]);
                                             else setSelectedPlugins(selectedPlugins.filter(p => p !== plugin));
                                         }}
                                         disabled={isRunning}
                                         className="accent-red-500"
                                     />
                                     <span className="capitalize">{plugin}</span>
                                 </label>
                             ))}
                        </div>
                     </div>
                )}
            </div>

            <Link href="/risk" className="w-full py-4 text-center font-bold tracking-widest rounded transition-all flex items-center justify-center bg-gray-800 hover:bg-gray-700 text-white mb-2 border border-gray-700">
                <ShieldAlert className="mr-2"/> RISK DASHBOARD
            </Link>

            <Link href="/history" className="w-full py-3 text-center font-bold tracking-widest rounded transition-all flex items-center justify-center bg-gray-900 hover:bg-gray-800 text-gray-400 hover:text-white mb-4 border border-gray-800">
                <Terminal className="mr-2" size={16}/> ATTACK HISTORY
            </Link>

            <button
                onClick={handleRun}
                disabled={isRunning}
                className={`w-full py-4 text-center font-bold tracking-widest rounded transition-all flex items-center justify-center
                    ${isRunning 
                        ? 'bg-gray-800 text-gray-500 cursor-not-allowed' 
                        : 'bg-red-600 hover:bg-red-700 text-white shadow-[0_0_15px_rgba(220,38,38,0.5)]'
                    }`}
            >
                {isRunning ? <RefreshCw className="animate-spin mr-2"/> : <Play className="mr-2"/>}
                {isRunning ? 'EXECUTING...' : 'LAUNCH ATTACK'}
            </button>
            
            {score !== null && (
                 <div className="mt-6 p-4 border border-gray-800 bg-gray-900 rounded text-center">
                    <h4 className="text-xs text-gray-400 uppercase">Success Score</h4>
                    <div className={`text-4xl font-bold mt-2 ${score > 0.7 ? 'text-red-500' : 'text-gray-500'}`}>
                        {score.toFixed(2)}
                    </div>
                 </div>
            )}
        </div>
      </div>

      {/* Main Content / Monitor */}
      <div className="lg:col-span-3 flex flex-col h-[90vh]">
         {/* Top Stats */}
         <div className="grid grid-cols-4 gap-4 mb-6">
            <StatsCard label="STATUS" value={status} icon={<Activity/>} active={status === 'RUNNING'} />
            <StatsCard label="ADAPTER" value={selectedModel ? "CONNECTED" : "WAITING"} icon={<Cpu/>} />
            <StatsCard label="SECURITY" value="ACTIVE" icon={<Lock/>} />
            <StatsCard label="TURNS" value={logs.length > 0 ? "LIVE" : "-"} icon={<Terminal/>} />
         </div>

         {/* Console */}
         <div className="flex-1 bg-black border border-gray-800 rounded-lg p-4 overflow-hidden flex flex-col relative shadow-inner">
             <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-red-900 to-transparent opacity-50"></div>
             <div className="flex justify-between items-center mb-4 border-b border-gray-800 pb-2">
                 <h2 className="text-sm font-bold text-gray-400 flex items-center">
                    <Terminal size={16} className="mr-2 text-red-500"/>
                    EXECUTION TRANSCRIPT
                 </h2>
                 <div className="flex space-x-2">
                    <span className="w-3 h-3 rounded-full bg-red-500 opacity-50"></span>
                    <span className="w-3 h-3 rounded-full bg-yellow-500 opacity-50"></span>
                    <span className="w-3 h-3 rounded-full bg-green-500 opacity-50"></span>
                 </div>
             </div>
             
             <div className="flex-1 overflow-y-auto space-y-2 font-mono text-sm p-2 custom-scrollbar">
                 {logs.length === 0 && (
                    <div className="text-gray-600 text-center mt-20 italic">
                        System Ready. Awaiting execution command.
                    </div>
                 )}
                 {logs.map((log, i) => (
                    <motion.div 
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        key={i} 
                        onClick={() => log.data && setSelectedLog(log.data)}
                        className={`flex items-start space-x-3 p-1 rounded hover:bg-gray-900/50 cursor-pointer transition-colors
                            ${log.type === 'error' ? 'text-red-400' : 
                              log.type === 'success' ? 'text-green-400 font-bold' : 'text-gray-300'}
                            ${log.data ? 'hover:bg-gray-800 border-l-2 border-transparent hover:border-red-500' : ''}`}
                    >
                        <span className="text-gray-600 text-xs mt-1 min-w-[60px]">{log.timestamp}</span>
                        <span>{log.message}</span>
                        {log.data && <span className="text-[10px] bg-gray-800 px-1 rounded text-gray-500 ml-auto">VIEW DETAILS</span>}
                    </motion.div>
                 ))}
                 <div ref={logsEndRef}/>
             </div>
         </div>
      </div>
    </div>
  );
}

function StatsCard({label, value, icon, active}: any) {
    return (
        <div className={`p-4 rounded border flex items-center justify-between ${active ? 'bg-red-900/20 border-red-900' : 'bg-gray-900/30 border-gray-800'}`}>
            <div>
                <p className="text-xs text-gray-500 font-bold mb-1">{label}</p>
                <p className={`text-lg font-bold ${active ? 'text-red-400' : 'text-white'}`}>{value}</p>
            </div>
            <div className={`${active ? 'text-red-500' : 'text-gray-600'}`}>
                {icon}
            </div>
        </div>
    )
}
