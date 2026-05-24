import subprocess
import time
import os
import sys

def run_scenario(api_key, headers, output_filename):
    print(f"--- Running scenario for {output_filename} ---")
    
    # 1. Setup environment variables
    env = os.environ.copy()
    if api_key is not None:
        env["API_KEY"] = api_key
    else:
        env.pop("API_KEY", None)
        
    # Ensure PYTHONPATH includes the current directory
    env["PYTHONPATH"] = "."
    
    # 2. Launch uvicorn server in the background
    python_path = os.path.join(".venv", "Scripts", "python.exe")
    server_process = subprocess.Popen(
        [python_path, "-m", "uvicorn", "web.api:app", "--port", "8000"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    # 3. Wait for the server to start up
    time.sleep(2)
    
    # 4. Construct and execute the curl command
    curl_args = ["curl.exe", "-X", "POST"]
    for k, v in headers.items():
        curl_args.extend(["-H", f"{k}: {v}"])
    curl_args.append("http://localhost:8000/api/alerts/some_decision_id/explain")
    
    print(f"Executing: {' '.join(curl_args)}")
    result = subprocess.run(curl_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False)
    
    # Combine stdout and stderr (simulating 2>&1)
    # The output from curl is typically binary or utf-8, but let's decode it safely
    combined_output = result.stdout + result.stderr
    
    # 5. Write to the evidence file
    os.makedirs("evidence", exist_ok=True)
    with open(output_filename, "wb") as f:
        f.write(combined_output)
        
    print(f"Captured output size: {len(combined_output)} bytes")
    
    # 6. Clean up the uvicorn process
    server_process.terminate()
    server_process.wait()
    print("Server stopped.\n")

if __name__ == "__main__":
    # Scenario 1: Valid API key provided
    run_scenario(
        api_key="test_valid_key",
        headers={"X-API-KEY": "test_valid_key"},
        output_filename="evidence/api-auth-success.txt"
    )
    
    # Scenario 2: Missing API key (but env var is set)
    run_scenario(
        api_key="test_valid_key",
        headers={},
        output_filename="evidence/api-auth-missing-key.txt"
    )
    
    # Scenario 3: API_KEY env var not set
    run_scenario(
        api_key=None,
        headers={},
        output_filename="evidence/api-auth-no-env-var.txt"
    )
