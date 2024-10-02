import json
import base64
import uuid
import requests
import time

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
                "taskName": "genie_disable",
                "subtaskName": "disableGenie",
                "contextId": contextId,
                "sessionId": "",
                "genieType": "internal",
                "startFrp": True,
                "hostFrpcConfig": "",
                "publicKey": "",
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
                "taskName": "genie_disable",
                "subtaskName": "enableGenie",
                "contextId": contextId,
                "genieType": "internal",
                "startFrp": True,
                "hostFrpcConfig": "",
                "userName": instance["user_name"],
                "password": "",
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
        
def execute(compute_resources):
    compute_resource_responses = []
    compute_resource_responses_failed = []
    
    for compute_resource in compute_resources:
        print(f"Disabling Genie for {compute_resource['compute_resource_id']}")
        instance = {}
        compute_response = {
            "compute_resource_id": compute_resource["compute_resource_id"]
        }
        if compute_resource["cloud"] == "aws":
            instance["user_name"] = "ec2-user"
        else:
            instance["user_name"] = "azureuser"

        if compute_resource["os"] == "windoes":
            instance["user_name"] = "GenieUser"

        instance['execution_id'] = str(uuid.uuid4())

        try:
            context_id = str(uuid.uuid4())
            if compute_resource["os"] == "linux":
                send_command_linux(compute_resource["db_vm_id"], context_id, instance)
            else:
                send_command_windows(compute_resource["db_vm_id"], context_id, instance)
            
            # Polling for status every 5 seconds, up to 20 times
            for _ in range(20):
                time.sleep(5)
                try:
                    status_response = fetch_cmd_status(compute_resource["db_vm_id"], instance['execution_id'])
                    if status_response in ["SUCCESS"]:
                        compute_response["status"] = "SUCCESS"
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

def main():
    try:
        with open('disable_compute_resources.json', 'r') as file:
            compute_resource_json = json.load(file)
            compute_resource_ids = list(compute_resource_json.keys())
    except FileNotFoundError:
        response = input("disable_compute_resources.json not found. Do you want to refer compute_resources.json for disabling? (yes/no): ").strip().lower()
        if response == 'yes' or response == 'y':
            try:
                with open('compute_resources.json', 'r') as file:
                    compute_resource_json = json.load(file)
                    compute_resource_ids = list(compute_resource_json.keys())
            except FileNotFoundError:
                raise Exception("compute_resources.json not found. Unable to proceed.")
        else:
            raise Exception("Operation aborted by the user.")
    
    compute_resources = []
    for compute_resource_id in compute_resource_ids:
        print(f"Getting compute info for {compute_resource_id}")
        try:
            compute_resource_metadata = get_compute_info(compute_resource_id)
        except BaseException as e:
            print()
            print(f"Genie disablement was not successful for compute resource {compute_resource_id}:")
            print(str(e))
            print()
            continue
        
        try:
            deploymentId = get_deployment_id(compute_resource_id)
            compute_resource_metadata["db_vm_id"] = deploymentId
        except Exception as e:
            print()
            print(f"Genie disablement was not successful for compute resource {compute_resource_id}:")
            print(str(e))
            print()
            continue

        compute_resources.append(compute_resource_metadata)

    print("Executing Genie disabling")
    _, compute_resource_responses_failed = execute(compute_resources)
    print("Disable complete")

    print()
    if len(compute_resource_responses_failed) > 0:
        print("Genie disablement failed for the following compute resources:")
        for failed_resource in compute_resource_responses_failed:
            print()
            print()
            print(f"Genie disablement was not successful for compute resource {failed_resource['compute_resource_id']}:")
            print(f"Status: {failed_resource['status']}")
            if 'output' in failed_resource:
                print(f"Output: {failed_resource['output']}")
            print()
            print()

if __name__ == "__main__":
    main()
