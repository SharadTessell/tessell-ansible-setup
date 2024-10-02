import json
import requests
import csv
import os

csv_file_path = 'service_instances_data.csv'
json_file_path = 'compute_resources.json'
inventory_file_path = os.path.expanduser('inventory')

starting_port = 22001

services_api_url = "http://tessell-database-system:8080/tessell-ops/services?page-size=1000"
service_instances_api_url_template = "http://tessell-database-system:8080/tessell-ops/services/{}/service-instances"

def fetch_service_ids(subscription_id):
    try:
        response = requests.get(services_api_url)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API: {e}")
        exit()

    extracted_services = []
    for item in data.get("response", []):
        if (
                item.get("subscriptionId") == subscription_id and
                item.get("status") == "READY" and
                item.get("engineType") != "SQLSERVER" and
                item.get("topology") == "single_instance"
        ):
            service_info = {
                "id": item.get("id"),
                "name": item.get("name"),
                "cloudType": item.get("metadata", {}).get("cloudType")  # Fetch cloud type
            }
            extracted_services.append(service_info)
    return extracted_services

def fetch_compute_res(service_ids):
    results = []
    for service in service_ids:
        service_id = service["id"]
        service_name = service["name"]
        try:
            response = requests.get(service_instances_api_url_template.format(service_id))
            response.raise_for_status()
            service_data = response.json()
            for instance in service_data.get("response", []):
                compute_resource_id = instance.get("computeResourceId")
                status = instance.get("status")
                role = instance.get("role")
                engine = instance.get("genericInfo", {}).get("softwareImage")
                results.append({
                    "service_id": service_id,
                    "service_name": service_name,
                    "computeResourceId": compute_resource_id,
                    "status": status,
                    "engine": engine,
                    "role": role,
                    "cloudType": service.get("cloudType")
                })
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data for service ID {service_id}: {e}")
    return results

def write_to_csv(data, filename):
    with open(filename, mode='w', newline='') as csv_file:
        fieldnames = ['Service ID', 'Name', 'Compute Resource ID', 'Status', 'Engine', 'Cloud Type']
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

        writer.writeheader()
        for entry in data:
            writer.writerow({
                'Service ID': entry['service_id'],
                'Name': entry['service_name'],
                'Compute Resource ID': entry['computeResourceId'],
                'Status': entry['status'],
                'Engine': entry['engine'],
                'Cloud Type': entry.get('cloudType')  # Add cloud type to CSV
            })

def create_json_and_inventory(service_data):
    compute_resources = {}
    unique_compute_resources = {}
    inventory_lines = set()
    engine_name_map = {}
    ssh_private_key_path = os.path.expanduser("~/PycharmProjects/Config_Management/tessell-ansible-setup/bulk_requests_genie/genie_bulk/genie_bulk_enable.pem")

    # Create the compute_resources.json content if there are any UP services
    if service_data:
        for item in service_data:
            uuid = item.get('computeResourceId')
            if not uuid:
                print(f"Key 'computeResourceId' not found in item: {item}")
                continue

            name = item['service_name'].replace(" ", "_")  # Replace spaces with underscores
            engine = item['engine'].replace(" ", "_")  # Replace spaces with underscores

            # If this compute resource ID is unique, add to the compute_resources dict
            if uuid not in compute_resources:
                compute_resources[uuid] = str(starting_port + len(compute_resources))

            # Prepare inventory entry with unique names
            unique_name = f"{name}_{engine}"
            engine_key = f"{engine}_{uuid}"  # Using engine and uuid to uniquely identify

            # Ensure unique names in inventory
            if engine_key not in engine_name_map:
                engine_name_map[engine_key] = unique_name
                inventory_line = (
                    f"{unique_name} ansible_host=localhost ansible_port={compute_resources[uuid]} "
                    f"ansible_user={'ec2-user' if item.get('cloudType') == 'aws' else 'azureuser'} "
                    f"ansible_ssh_private_key_file={ssh_private_key_path}"
                )
                inventory_lines.add(inventory_line)
    with open(json_file_path, 'w') as json_file:
        json.dump(compute_resources, json_file, indent=4)
    print(
        f"compute_resources.json has been created with the following content:\n{json.dumps(compute_resources, indent=4)}"
    )
    with open(inventory_file_path, 'w') as inventory_file:
        inventory_file.write('\n'.join(inventory_lines) + '\n')  # Ensure there’s a newline at the end
    print(f"Inventory file has been created at {inventory_file_path} with the following content:\n")
    print('\n'.join(inventory_lines))

def main():
    target_subscription_id = input("Please enter the Subscription ID: ")
    service_ids = fetch_service_ids(target_subscription_id)
    service_instances_data = fetch_compute_res(service_ids)
    write_to_csv(service_instances_data, csv_file_path)
    print(f"Service instances data written to {csv_file_path}")
    create_json_and_inventory(service_instances_data)

if __name__ == "__main__":
    main()

