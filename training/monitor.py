"""NEXUS Training Monitor — loss tracking, VRAM, overfitting detection, Drive backup."""
import json, shutil, torch
from pathlib import Path
from datetime import datetime
from transformers import TrainerCallback, TrainerState, TrainerControl

DRIVE_ROOT = "/content/drive/MyDrive/nexus-agent"
LOG_FILE   = "logs/training/metrics.jsonl"

class NEXUSMonitorCallback(TrainerCallback):
    def __init__(self):
        self.train_losses=[]; self.eval_losses=[]; self.best_eval=float("inf")
        Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
        print("  [Monitor] NEXUS callback aktif ✓")

    def on_log(self, args, state:TrainerState, control:TrainerControl, logs=None, **kw):
        if not logs: return
        row={"ts":datetime.now().strftime("%H:%M:%S"),"step":state.global_step,
             "epoch":round(state.epoch or 0,3)}
        row.update({k:round(v,6) if isinstance(v,float) else v for k,v in logs.items()})
        with open(LOG_FILE,"a",encoding="utf-8") as f: f.write(json.dumps(row)+"\n")
        if "loss" in logs: self.train_losses.append(logs["loss"])
        if "eval_loss" in logs:
            ev=logs["eval_loss"]; self.eval_losses.append(ev)
            self._check(logs.get("loss"),ev,state.global_step)
            if ev<self.best_eval: self.best_eval=ev; print(f"\n  ⭐ Best eval_loss={ev:.4f} [step {state.global_step}]")

    def on_step_end(self,args,state,control,**kw):
        if state.global_step%50!=0 or not torch.cuda.is_available(): return
        a=torch.cuda.memory_allocated(0)/1e9; r=torch.cuda.memory_reserved(0)/1e9
        l=f"{self.train_losses[-1]:.4f}" if self.train_losses else "—"
        print(f"  [Step {state.global_step:4d}] loss={l}  VRAM={a:.1f}/{r:.1f}GB")

    def on_epoch_end(self,args,state,control,**kw):
        epoch=int(state.epoch or 0)
        avg_str = f"{sum(self.train_losses[-100:])/min(len(self.train_losses),100):.4f}" if self.train_losses else "N/A (belum ada log step)"
        best_str = f"{self.best_eval:.4f}" if self.best_eval != float("inf") else "N/A"
        print(f"\n  {'═'*50}\n  EPOCH {epoch} | avg_loss={avg_str} | best_eval={best_str}")
        self._backup(args.output_dir,epoch); print(f"  {'═'*50}\n")

    def _check(self,train,ev,step):
        if ev<0.4: print(f"\n  ⚠️  [step {step}] eval={ev:.4f} < 0.4 → kemungkinan OVERFIT")
        if train and (ev-train)>0.5: print(f"\n  ⚠️  [step {step}] Gap besar: train={train:.4f} eval={ev:.4f}")
        if len(self.eval_losses)>=3 and all(self.eval_losses[-3+i]<=self.eval_losses[-3+i+1] for i in range(2)):
            print(f"\n  ⚠️  [step {step}] Eval loss naik 3x — pertimbangkan early stop")

    def _backup(self,output_dir,epoch):
        ckpts=sorted(Path(output_dir).glob("checkpoint-*"),key=lambda p:int(p.name.split("-")[-1]))
        if not ckpts: return
        try:
            shutil.copytree(str(ckpts[-1]),f"{DRIVE_ROOT}/checkpoints/epoch_{epoch}_{ckpts[-1].name}",dirs_exist_ok=True)
            print(f"  💾 Backed up to Drive")
        except Exception as e: print(f"  ⚠️  Backup failed: {e}")

def plot_loss(log_file=LOG_FILE):
    try: import matplotlib.pyplot as plt
    except: print("pip install matplotlib"); return
    st,lt,se,le=[],[],[],[]
    with open(log_file,encoding="utf-8") as f:
        for line in f:
            m=json.loads(line)
            if "loss" in m and "eval_loss" not in m: st.append(m["step"]); lt.append(m["loss"])
            if "eval_loss" in m: se.append(m["step"]); le.append(m["eval_loss"])
    fig,ax=plt.subplots(figsize=(12,5))
    ax.plot(st,lt,label="Train",color="#00ff88",lw=1.5)
    ax.plot(se,le,label="Eval",color="#ff4444",lw=2,marker="o",ms=4)
    ax.axhline(0.75,color="yellow",ls="--",alpha=0.7,label="Target 0.75")
    ax.axhline(0.4,color="red",ls="--",alpha=0.4,label="Overfit 0.4")
    ax.set(xlabel="Steps",ylabel="Loss",title="NEXUS Training Curves"); ax.legend(); ax.grid(alpha=0.3)
    ax.set_facecolor("#0d0d0d"); fig.patch.set_facecolor("#1a1a1a")
    plt.savefig("logs/training/loss_curve.png",dpi=120,bbox_inches="tight"); plt.show()
