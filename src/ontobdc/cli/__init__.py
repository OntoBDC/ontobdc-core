import sys
import argparse
import subprocess
import os
from ontobdc.run.run import main as run_main


def check_main(args):
    # Get the directory of this file (src/ontobdc/cli)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Path to check.sh (src/ontobdc/check/check.sh)
    # cli/.. -> src/ontobdc -> check -> check.sh
    check_script = os.path.join(current_dir, "..", "check", "check.sh")
    
    if not os.path.exists(check_script):
        print(f"Error: check.sh not found at {check_script}")
        sys.exit(1)
        
    # Build command arguments
    cmd = [check_script]
    if args.repair:
        cmd.append("--repair")
    
    # Execute the shell script
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except Exception as e:
        print(f"Error executing check script: {e}")
        sys.exit(1)

def setup_main(args):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    setup_script = os.path.join(current_dir, "setup.sh")
    
    if not os.path.exists(setup_script):
        print(f"Error: setup.sh not found at {setup_script}")
        sys.exit(1)

    cmd = [setup_script, args.engine]
    
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except Exception as e:
        print(f"Error executing setup script: {e}")
        sys.exit(1)

def dev_command(action, args):
    # Map dev commands to their scripts in src/ontobdc/dev
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # cli/.. -> src/ontobdc -> dev -> action.sh
    script_path = os.path.join(current_dir, "..", "dev", f"{action}.sh")
    
    if not os.path.exists(script_path):
        print(f"Error: {action}.sh not found at {script_path}")
        sys.exit(1)

    # We need to pass all arguments to the script
    # Since we are inside python, we need to reconstruct argv
    # But args here is from argparse.
    # The simplest way is to just pass sys.argv minus the first two elements (prog name and command)
    # However, for robustness let's just use the raw arguments
    
    cmd = [script_path] + sys.argv[2:]
    
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except Exception as e:
        print(f"Error executing {action} script: {e}")
        sys.exit(1)

def main():
    # If no args, print help
    if len(sys.argv) == 1:
        print("OntoBDC CLI")
        print("Available commands: run, check, setup, commit, branch, plan")
        sys.exit(0)

    cmd = sys.argv[1]
    
    if cmd == "run":
        # Pass control to existing run module
        # run.py expects sys.argv to start with script name, then arguments
        # If we call `ontobdc run`, sys.argv is ['ontobdc', 'run', ...]
        # run.py might be interpreting 'run' as the capability ID if it just looks at argv[1]
        
        # We need to shift sys.argv so run.py sees ['ontobdc', ...] (arguments after run)
        # Essentially, we want to hide the 'run' subcommand from the run module
        
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        run_main()
    elif cmd == "check":
        parser = argparse.ArgumentParser(description="System Check")
        parser.add_argument("--repair", action="store_true", help="Attempt to repair issues")
        # Parse only arguments after 'check'
        args, unknown = parser.parse_known_args(sys.argv[2:])
        check_main(args)
    elif cmd == "setup":
        parser = argparse.ArgumentParser(description="Setup Engine")
        parser.add_argument("engine", help="Engine name (e.g. venv, colab)")
        args, unknown = parser.parse_known_args(sys.argv[2:])
        setup_main(args)
    elif cmd == "commit":
        dev_command("commit", None)
    elif cmd == "branch":
        dev_command("branch", None)
    elif cmd == "plan":
        # plan is under run/plan.sh, not dev
        # But wait, run module handles run.py. Does it handle plan?
        # In ontobdc.sh, plan calls run/plan.sh
        # Let's handle plan similar to run or via shell script wrapper?
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        plan_script = os.path.join(current_dir, "..", "run", "plan.sh")
        
        if not os.path.exists(plan_script):
             print(f"Error: plan.sh not found at {plan_script}")
             sys.exit(1)
             
        cmd_args = [plan_script] + sys.argv[2:]
        try:
            subprocess.run(cmd_args, check=True)
        except subprocess.CalledProcessError as e:
            sys.exit(e.returncode)
        
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()
