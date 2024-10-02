import json
import requests
import csv

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
                item.get("topology") == "single_instance"
        ):
            service_info = {
                "id": item.get("id"),
                "name": item.get("name")
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
                # Extract engine from genericInfo
                engine = instance.get("genericInfo", {}).get("softwareImage")
                results.append({
                    "service_id": service_id,
                    "service_name": service_name,
                    "computeResourceId": compute_resource_id,
                    "status": status,
                    "engine": engine
                })
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data for service ID {service_id}: {e}")

    return results
def write_to_csv(data, filename):
    with open(filename, mode='w', newline='') as csv_file:
        fieldnames = ['Service ID', 'Name', 'Compute Resource ID', 'Status', 'Engine']
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

        writer.writeheader()
        for entry in data:
            writer.writerow({
                'Service ID': entry['service_id'],
                'Name': entry['service_name'],
                'Compute Resource ID': entry['computeResourceId'],
                'Status': entry['status'],
                'Engine': entry['engine']
            })

target_subscription_id = input("Please enter the Subscription ID: ")
service_ids = fetch_service_ids(target_subscription_id)
service_instances_data = fetch_compute_res(service_ids)

csv_filename = 'service_instances_data.csv'
write_to_csv(service_instances_data, csv_filename)
print(f"Service instances data written to {csv_filename}")
