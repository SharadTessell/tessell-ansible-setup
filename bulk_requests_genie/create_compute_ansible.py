# import json
# import os
#
# # Define file paths
# csv_file_path = 'abc.csv'
# json_file_path = 'compute_resourcesss.json'
# inventory_file_path = os.path.expanduser('~/ansible-setup/inventoryyy')
#
# # Define starting port numbers
# starting_port = 22001
#
# # Ask user for cloud type
# cloud_type = input("Enter cloud type (AWS/AZURE): ").strip().upper()
# ansible_user = "ec2-user" if cloud_type == "AWS" else "azureuser"
#
# # Read the UUIDs from the CSV file
# with open(csv_file_path, 'r') as file:
#     uuids = [line.strip() for line in file.readlines()]
#
# # Create the compute_resources.json content
# compute_resources = {uuid: str(starting_port + i) for i, uuid in enumerate(uuids)}
#
# # Write the JSON data to compute_resources.json
# with open(json_file_path, 'w') as json_file:
#     json.dump(compute_resources, json_file, indent=4)
#
# print(f"compute_resources.json has been created with the following content:\n{json.dumps(compute_resources, indent=4)}")
#
# # Create the inventory content
# inventory_lines = []
# for i, uuid in enumerate(uuids):
#     ansible_port = str(starting_port + i)
#     inventory_line = (f"{uuid} ansible_host=localhost ansible_port={ansible_port} "
#                       f"ansible_user={ansible_user} "
#                       f"ansible_ssh_private_key_file=/Users/sharaddubey/Downloads/bulk_requests_genie/genie_bulk/genie_bulk_enable.pem")
#     inventory_lines.append(inventory_line)
#
# # Write the inventory data to ~/ansible-setup/inventory
# with open(inventory_file_path, 'w') as inventory_file:
#     # Join lines with newline and write without adding extra characters
#     inventory_file.write('\n'.join(inventory_lines) + '\n')  # Ensure there’s a newline at the end
#
# print(f"Inventory file has been created at {inventory_file_path} with the following content:\n")
# print('\n'.join(inventory_lines))


import json
import os
import csv

# Define file paths
csv_file_path = 'service_instances_data.csv'
json_file_path = 'compute_resources.json'
inventory_file_path = os.path.expanduser('inventory')

# Define starting port numbers
starting_port = 22001

# Ask user for cloud type
cloud_type = input("Enter cloud type (AWS/AZURE): ").strip().upper()
ansible_user = "ec2-user" if cloud_type == "AWS" else "azureuser"

# Read the CSV file to filter by status
service_data = []
with open(csv_file_path, 'r') as file:
    reader = csv.DictReader(file)
    for row in reader:
        if row['Status'] == 'UP':
            service_data.append(row)
        else:
            print(
                f"Skipping: {row['Name']} with Compute Resource ID: {row['Compute Resource ID']} - Status: {row['Status']}")

# Prepare the UUIDs and the corresponding status
compute_resources = {}
uuids = []

# Create the compute_resources.json content if there are any UP services
if service_data:
    for i, item in enumerate(service_data):
        uuid = item['Compute Resource ID']
        name = item['Name'].replace(" ", "_")  # Replace spaces with underscores
        engine = item['Engine'].replace(" ", "_")  # Replace spaces with underscores
        compute_resources[uuid] = str(starting_port + i)
        formatted_uuid = f"{name}_{engine}_{uuid}"
        uuids.append((formatted_uuid, uuid))  # Store formatted UUID for inventory

    # Ask for permission to create the JSON
    permission = input("Do you want to create the compute_resources.json file? (yes/no): ").strip().lower()

    if permission == 'yes':
        # Write the JSON data to compute_resources.json
        with open(json_file_path, 'w') as json_file:
            json.dump(compute_resources, json_file, indent=4)

        print(
            f"compute_resources.json has been created with the following content:\n{json.dumps(compute_resources, indent=4)}")

        # Create the inventory content
        inventory_lines = []
        for formatted_uuid, uuid in uuids:
            ansible_port = str(starting_port + uuids.index((formatted_uuid, uuid)))
            inventory_line = (f"{formatted_uuid} ansible_host=localhost ansible_port={ansible_port} "
                              f"ansible_user={ansible_user} "
                              f"ansible_ssh_private_key_file=/Users/sharaddubey/Downloads/bulk_requests_genie/genie_bulk/genie_bulk_enable.pem")
            inventory_lines.append(inventory_line)

        # Write the inventory data to ~/ansible-setup/inventory
        with open(inventory_file_path, 'w') as inventory_file:
            inventory_file.write('\n'.join(inventory_lines) + '\n')  # Ensure there’s a newline at the end

        print(f"Inventory file has been created at {inventory_file_path} with the following content:\n")
        print('\n'.join(inventory_lines))
    else:
        print("Operation canceled by the user.")
else:
    print("No services with status UP found. JSON and inventory file creation skipped.")
