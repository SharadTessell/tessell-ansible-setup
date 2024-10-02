import json
import base64
import uuid
import requests
import time
import os
import shutil
import subprocess
import argparse
import stat

tgs_url = "http://tessell-tgs-local.tgs.svc.cluster.local:8080"

def send_command_linux(dbVmId, contextId, instance):
    try:
        timeout = 60

        # Create the payload object
        payload_object = {
            "vm_ip": "",
            "user": instance["user_name"],
            "task_id": contextId,
            "task_json": {
                "taskId": contextId,
                "return_output": True,
                "workName": "executeTask",
                "engineType": "host",
                "isVaultNeeded": "false",
                "taskName": "genie_enable",
                "subtaskName": "enableGenie",
                "contextId": contextId,
                "sessionId": "",
                "genieType": "internal",
                "startFrp": True,
                "hostFrpcConfig": instance["host_config"],
                "publicKey": instance["public_key"],
                "genieUser": instance["user_name"],
                "sshdPort": "",
                "secretKey": "",
                "frpsAddr": "",
                "frpsPort": "",
                "token": "",
                "winrmPort": "",
                "rdpPort": "",
                "userName": "",
                "password": ""
            }
        }

        payload_bytes = json.dumps(payload_object).encode('utf-8')
        payload_string = base64.b64encode(payload_bytes).decode('utf-8')

        # Create the final payload for the POST request
        final_payload = {
            "dbVmId": dbVmId,
            "cmdString": "runTessellLambda",
            "payload": payload_string,
            "executionId": instance['execution_id'],
            "timeout": timeout
        }

        # Make the POST request
        response = requests.post(f"{tgs_url}/command", json=final_payload)

        # Check the response
        if response.status_code >= 205:
            raise Exception(f"Request failed with status code {response.status_code}")
    except Exception as e:
        raise Exception(f"Unable to send command via TGS. Error: {str(e)}")

def send_command_windows(dbVmId, contextId, instance):
    try:
        timeout = 60

        # Create the payload object
        payload_object = {
            "user": instance["user_name"],
            "task_id": contextId,
            "task_json": {
                "taskId": contextId,
                "return_output": True,
                "workName": "executeTask",
                "engineType": "host",
                "rdpPort": "",
                "isVaultNeeded": "false",
                "taskName": "genie_enable",
                "subtaskName": "enableGenie",
                "contextId": contextId,
                "genieType": "internal",
                "startFrp": True,
                "hostFrpcConfig": instance["host_config"],
                "userName": instance["user_name"],
                "password": instance["password"],
                "sshdPort": "",
                "secretKey": "",
                "frpsAddr": "",
                "frpsPort": "",
                "token": "",
                "winrmPort": "",
                "rdpPort": "",
                "userName": "",
                "password": ""
            }
        }

        payload_bytes = json.dumps(payload_object).encode('utf-8')
        payload_string = base64.b64encode(payload_bytes).decode('utf-8')

        # Create the final payload for the POST request
        final_payload = {
            "dbVmId": dbVmId,
            "cmdString": "runTessellLambda",
            "payload": payload_string,
            "executionId": instance['execution_id'],
            "timeout": timeout
        }

        # Make the POST request
        response = requests.post(f"{tgs_url}/command", json=final_payload)

        # Check the response
        if response.status_code > 205:
            raise Exception(f"Request failed with status code {response.status_code}")

    except Exception as e:
        raise Exception(f"Unable to send command via TGS. Error: {str(e)}")

def fetch_cmd_status(taId, executionId):
    try:
        response = requests.get(f"{tgs_url}/status/{taId}/{executionId}")
    except requests.exceptions.RequestException as err:
        raise Exception(f"Error in fetching cmd status over TGS while Enabling Genie, Error: {str(err)}")

    tgs_resp = response.json()

    if tgs_resp['status'] in ['SUCCESS']:
        if tgs_resp['output'] is None:
            raise Exception("TGS Output not available")

        tgs_output_string = base64.b64decode(tgs_resp['output']).decode('utf-8')
        try:
            tgs_output = json.loads(tgs_output_string)
        except json.JSONDecodeError as err:
            raise Exception("Error unmarshalling tgs output")

        if tgs_output.get('statusCode') and tgs_output['statusCode'] < 205 and tgs_resp['status'] == 'SUCCESS':
            return "SUCCESS"
        else:
            body = tgs_output.get('body', {})
            cmd_output = body.get('message')
            raise Exception(f"Cmd failed in VM for Enabling Genie, Error: {cmd_output}")
    
    if tgs_resp['status'] in ["FAILED"]:
        raise Exception(f"Cmd failed in VM for Enabling Genie, Error: {tgs_resp['error']}")
    
    return "RUNNING"
        
def create_configs_token(server_addr, compute_resource_id, local_port, bind_port):
    instance = {}

    visitor_config_template = """
    [common]
    server_addr = {server_addr}
    server_port = 7000
    authentication_method = token
    token = fxr02OjUi2ZAqrDh

    [secret_ssh_{id}_visitor]
    type = stcp
    role = visitor
    server_name = host_{id}
    sk = secret123
    bind_addr = 127.0.0.1
    bind_port = {bind_port}
    """

    visitor_config = visitor_config_template.format(
        server_addr=server_addr,
        id=compute_resource_id,
        bind_port=bind_port
    ).replace("\t", "")

    instance["visitor_config"] = visitor_config

    host_config_template = """
    [common]
    server_addr = {server_addr}
    server_port = 7000
    authentication_method = token
    token = fxr02OjUi2ZAqrDh

    [host_{id}]
    type = stcp
    sk = secret123
    local_ip = 127.0.0.1
    local_port = {local_port}
    """

    host_config = host_config_template.format(
        server_addr=server_addr,
        id=compute_resource_id,
        local_port=local_port
    ).replace("\t", "")

    instance["host_config"] = host_config

    return instance

def execute(compute_resources, public_key, windows_password):
    compute_resource_responses = []
    compute_resource_responses_failed = []
    
    for compute_resource in compute_resources:
        print(f"Enabling Genie for {compute_resource['compute_resource_id']}")
        port = 22
        bind_port = compute_resource["bind_port"]
        if compute_resource["os"] == "windows":
            port = 3389

        instance = create_configs_token(
            compute_resource["server_addr"],
            compute_resource["compute_resource_id"],
            port,
            bind_port,
        )

        compute_response = {}
        compute_response["compute_resource_id"] = compute_resource["compute_resource_id"]
        compute_response["bind_port"] = bind_port
        compute_response["os"] = compute_resource["os"]
        compute_response["password"] = windows_password

        if compute_resource["cloud"] == "aws":
            instance["user_name"] = "ec2-user"
            compute_response["user_name"] = "ec2-user"
        else:
            instance["user_name"] = "azureuser"
            compute_response["user_name"] = "azureuser"

        if compute_resource["os"] == "linux":
            instance["public_key"] = public_key
        else:
            instance["user_name"] = "GenieUser"
            instance["password"] = windows_password

        instance['execution_id'] = str(uuid.uuid4())

        try:
            context_id = str(uuid.uuid4())
            if compute_resource["os"] == "linux":
                send_command_linux(compute_resource["db_vm_id"], context_id, instance)
            else:
                send_command_windows(compute_resource["db_vm_id"], context_id, instance)
            
            compute_response["visitor_config"] = instance["visitor_config"]
            
            # Polling for status every 5 seconds, up to 20 times
            for _ in range(20):
                time.sleep(5)
                try:
                    status_response = fetch_cmd_status(compute_resource["db_vm_id"], instance['execution_id'])
                    if status_response in ["SUCCESS"]:
                        compute_response["status"] = "SUCCESS"
                        compute_response["visitor_config"] = instance["visitor_config"]
                        break
                except Exception as e:
                    compute_response["status"] = "FAILED"
                    compute_response["output"] = str(e)
                    break
            else:
                compute_response["status"] = "TIMED_OUT"
                compute_response["output"] = "Get TGS status timed out"

        except Exception as e:
            compute_response["status"] = "COMMAND_NOT_SEND"
            compute_response["output"] = str(e)

        if compute_response["status"] == "SUCCESS":
            compute_resource_responses.append(compute_response)
        else:
            compute_resource_responses_failed.append(compute_response)

    return compute_resource_responses, compute_resource_responses_failed

def create_genie_bulk_zip(compute_responses, private_key_file_name, parent_folder, ssh_commands = {}):    
    # Iterate over compute_responses and create files
    for compute_resource in compute_responses:
        frpc_file_name = f"frpc_{compute_resource['compute_resource_id']}.ini"
        file_path = os.path.join(parent_folder, frpc_file_name)
        
        with open(file_path, 'w') as file:
            file.write(compute_resource["visitor_config"])
        
        bind_port = compute_resource["bind_port"]

        if compute_resource["os"] == "linux":
            ssh_command = f"ssh -i {private_key_file_name} -p {bind_port} {compute_resource['user_name']}@127.0.0.1"
            ssh_commands[compute_resource["compute_resource_id"]] = {
                "ssh_command": ssh_command
            }
        else:
            rdp_session = {
                "host": f"127.0.0.1:{bind_port}",
                "username": "GenieUser",
                "password": compute_resource["password"]
            }
            ssh_commands[compute_resource["compute_resource_id"]] = {
                "rdp_session": rdp_session
            }
        
    # Write the JSON file
    json_file_path = os.path.join(parent_folder, "ssh_commands.json")

    with open(json_file_path, 'w') as json_file:
        json.dump(ssh_commands, json_file, indent=4)
    
    # Bash script content
    bash_script = f"""#!/bin/bash

# Create frpc_logs directory if it doesn't exist
if [ ! -d "frpc_logs" ]; then
    mkdir frpc_logs
fi

# Clean up all frpcs if fresh_run is True
echo "Cleaning up all frpc instances..."
pkill -f "frpc"  # This command stops all running frpc processes

# Iterate over all frpc.ini files and execute frpc -c for each in the background
for file in *.ini; do
    echo "Processing $file..."

    # Check if frpc is already running for this configuration
    if pgrep -f "frpc -c $file" > /dev/null; then
        echo "frpc with $file is already running."
        continue
    fi

    # Start frpc in the background and log output
    nohup frpc -c "$file" > "frpc_logs/$file.log" 2>&1 &
    
    if [ $? -eq 0 ]; then
        echo "Started frpc with $file"
    else
        echo "Failed to start frpc with $file. Check frpc_logs/$file.log for details."
    fi
done

echo "All frpc instances processed."
"""

    # Write the bash script to the parent folder
    bash_script_path = os.path.join(parent_folder, "run_frpc.sh")
    with open(bash_script_path, 'w') as script_file:
        script_file.write(bash_script)
    
    # Make the bash script executable
    os.chmod(bash_script_path, 0o755)

def get_compute_info(compute_resource_id):
    try:
        # Making the GET request
        response = requests.get(f"http://tessell-database-system:8080/tessell-ops/compute-resources/{compute_resource_id}")
        # Checking if the request was successful (status code 200)
        if response.status_code == 200:
            # Parsing the JSON response
            data = response.json()
            
            # Extracting OS and Cloud information
            os_type = data["osInfo"]["type"].lower()  # Convert to lowercase as per your requirement
            cloud_parts = data["cloudLocation"].split("/")
            cloud = cloud_parts[0].lower()  # Extracting the cloud part and converting to lowercase
            tenantId = data["tenantId"]
            
            # Creating the transformed dictionary
            transformed_data = {
                "compute_resource_id": compute_resource_id,
                "os": os_type,
                "cloud": cloud,
                "tenant_id": tenantId
            }
            
            return transformed_data
        else:
            raise Exception(f"Error: Failed to retrieve compute metadata. Status code: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to retrieve compute metadata. Error: {e}")
    
def get_deployment_id(compute_resource_id):
    try:
        # Making the GET request
        response = requests.get(f"http://tessell-database-system:8080/tessell-ops/compute-resources/{compute_resource_id}/metadata/version/1")
        
        # Checking if the request was successful (status code 200)
        if response.status_code == 200:
            data = response.json()
            value = data["metadata"]["data"]["deploymentId"]
            return value
        else:
            raise Exception(f"Error: Failed to retrieve deployment id. Status code: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to retrieve deployment id. Error: {e}")

def get_private_cp_dp(tenant_id):
    try:
        url = f"http://tessell-tenant:8080/tessell-ops/v2/tenants?tenant-id={tenant_id}"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            value = data['response'][0]['metadata']['enablePrivateCpDpCommunication']
            
            return value
        else:
            return False
            
    except requests.exceptions.RequestException as e:
        return False

def get_frps_server(resource_type):
    try:
        # Making the GET request
        response = requests.get(f"http://tessell-infra:8080/tessell-ops/infra/resources?resource-type={resource_type}")
        
        # Checking if the request was successful (status code 200)
        if response.status_code == 200:
            data = response.json()
            value = data[0]["resourceInfo"]["parameters"]["frpsDomainName"]["value"]
            return value
        else:
            raise Exception(f"Error: Failed to retrieve FRPS Server address from infra resource API. Status code: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error: {e}")
    
def get_private_frps_address(compute_resource_id):
    try:
        url = f'http://tessell-database-system:8080/compute-resources/{compute_resource_id}/hosting-info'
        response = requests.get(url)

        if response.status_code == 200:
            hosting_info = response.json()
            
            if hosting_info.get('infraConfig') and hosting_info['infraConfig'].get('networkProfile'):
                vpc_endpoints = hosting_info['infraConfig']['networkProfile'].get('vpcEndpoints')
                
                if vpc_endpoints and 'TESSELL_FRPS' in vpc_endpoints:
                    frps_config = vpc_endpoints['TESSELL_FRPS']
                    
                    if frps_config and not frps_config.get('privateDnsEnabled', False):
                        dns_entries = frps_config.get('dnsEntries')
                        
                        if dns_entries and len(dns_entries) > 0:
                            dns_name = dns_entries[0].get('dnsName')
                            
                            if dns_name:
                                return True, dns_name
                                
        return False, ""
    
    except requests.exceptions.RequestException as e:
        return False, ""

def generate_ssh_keys(fresh_run, parent_folder_path):
    try:
        private_key_path = os.path.join(parent_folder_path, "genie_bulk_enable.pem")
        public_key_path = os.path.join(parent_folder_path, "genie_bulk_enable.pub")

        if fresh_run:
            print("Generating Keys")

            subprocess.run([
                "ssh-keygen", "-t", "rsa", "-b", "2048",
                "-m", "PEM",
                "-f", private_key_path,
                "-q", "-N", ""  # -q for quiet mode, -N "" for no passphrase
            ])

            os.rename(private_key_path + ".pub", public_key_path)
            os.chmod(private_key_path, stat.S_IRUSR)
            print(f"SSH key pair created: {private_key_path} (private) and {public_key_path} (public)")
            return private_key_path, public_key_path
        else:
            if not os.path.isfile(private_key_path) or not os.path.isfile(public_key_path):
                raise Exception(f"One of the SSH key files does not exist. Please run the script with --fresh_run")
            return private_key_path, public_key_path
            
    except Exception as e:
        raise Exception(f"Unable to generate SSH key. Error: {str(e)}")
    
def get_current_state(compute_resource_json, parent_folder_path): 
    json_file_path = os.path.join(parent_folder_path, "ssh_commands.json")
    if not os.path.isfile(json_file_path):
        raise Exception(f"ssh_commands.json file doesnt exist in genie_bulk. Please run the script with --fresh_run")
    
    with open(json_file_path, 'r') as file:
        ssh_commands = json.load(file)

     # Remove entries from compute_resource_id_json where the computeResourceId is a key in ssh_commands
    new_compute_resource_json = {compute_resource_id: bind_port for compute_resource_id, bind_port in compute_resource_json.items() if compute_resource_id not in ssh_commands}
    return new_compute_resource_json, ssh_commands

def create_parent_folder(fresh_run):
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_folder_path = os.path.join(script_dir, "genie_bulk")

    if fresh_run:
        if os.path.exists(parent_folder_path):
            shutil.rmtree(parent_folder_path)
        os.makedirs(parent_folder_path)
    else:
        if not os.path.exists(parent_folder_path):
            raise Exception(f"genie_bulk folder doesnt exist. Please run the script with --fresh_run")
    
    return parent_folder_path

def main(fresh_run, cloud):
    try:
        with open('compute_resources.json', 'r') as file:
            compute_resource_json = json.load(file)
            ssh_commands = {}
        # Check if all ports are unique
        ports = list(compute_resource_json.values())
        if not len(ports) == len(set(ports)):
            raise Exception("Some bind ports are duplicates.")
    except FileNotFoundError:
        raise Exception("The file 'compute_resources.json' does not exist.")
    
    parent_folder_path = create_parent_folder(fresh_run)

    if not fresh_run:
        compute_resource_json, ssh_commands = get_current_state(compute_resource_json, parent_folder_path)

    private_key_path, public_key_path = generate_ssh_keys(fresh_run, parent_folder_path)

    with open(public_key_path, 'r') as pub_key_file:
        _public_key = pub_key_file.read().strip().split(' ', 2)[:2]
        public_key = ' '.join(_public_key)
    
    windows_password = "windows123"
    if cloud.lower() == 'aws':
        resource_type = "AWS_EKS"
    else:
        resource_type = "AZURE_AKS"
    frps_address = get_frps_server(resource_type)
    compute_resources = []
    for compute_resource_id, bind_port in compute_resource_json.items():
        print(f"Getting compute info for {compute_resource_id}")
        try:
            compute_resource_metadata = get_compute_info(compute_resource_id)
        except BaseException as e:
            print()
            print(f"Genie enablement was not successful for compute resource {compute_resource_id}:")
            print(str(e))
            print()
            continue
        
        try:
            deploymentId = get_deployment_id(compute_resource_id)
            compute_resource_metadata["db_vm_id"] = deploymentId
        except Exception as e:
            print()
            print(f"Genie enablement was not successful for compute resource {compute_resource_id}:")
            print(str(e))
            print()
            continue

        compute_resource_metadata["server_addr"] = frps_address
        compute_resource_metadata["bind_port"] = bind_port
        privatecpdp = get_private_cp_dp(compute_resource_metadata["tenant_id"])
        if privatecpdp:
            dns_name_set, dns_name = get_private_frps_address(compute_resource_metadata["compute_resource_id"])
            if dns_name_set:
                compute_resource_metadata["server_addr"] = dns_name
        compute_resources.append(compute_resource_metadata)

    print("Executing Genie requests")
    compute_resource_responses, compute_resource_responses_failed = execute(compute_resources, public_key, windows_password)
    print("Execution complete")
    print("Creating configuration file")
    create_genie_bulk_zip(compute_resource_responses, private_key_path, parent_folder_path, ssh_commands)
    print("Configuration file created for successful genies")
    print()
    if len(compute_resource_responses_failed) > 0:
        print("Genie enablement failed for the following compute resources:")
        for failed_resource in compute_resource_responses_failed:
            print()
            print(f"Genie enablement was not successful for compute resource {failed_resource['compute_resource_id']}:")
            print(f"Status: {failed_resource['status']}")
            if 'output' in failed_resource:
                print(f"Output: {failed_resource['output']}")
            print()

def main2(cloud_provider, fresh_run):
    print("cloud_provider:", cloud_provider)
    print("fresh_run:", fresh_run)

if __name__ == "__main__":
    # Prompt for cloud provider
    cloud_provider = input("Enter the cloud provider (AWS or Azure): ").strip()
    while cloud_provider.lower() not in ['aws', 'azure']:
        print("Invalid cloud provider. Please enter 'AWS' or 'Azure'.")
        cloud_provider = input("Enter the cloud provider (AWS or Azure): ").strip()

    print()
    print("########")
    print("Fresh run will try to enable Genie for instances mentioned in compute_resource.json irrespective of past runs")
    print("########")
    print()
     # Prompt for fresh run mode
    fresh_run_input = input("Enable fresh run mode? (yes/no): ").strip().lower()
    while fresh_run_input.lower() not in ['yes', 'no']:
        print("Invalid input. Please enter 'yes' or 'no'.")
        fresh_run_input = input("Enable fresh run mode? (yes/no): ").strip().lower()
    fresh_run_bool = fresh_run_input.lower() == 'yes'

    main(cloud_provider, fresh_run_bool)
