
import os
import time
import json
import google.api_core.exceptions
from flask import Flask, jsonify
from google.cloud import compute_v1
from itertools import cycle

app = Flask(__name__)

# --- Structured Logging Helper ---
def log_structured(message, severity="INFO", **kwargs):
    """Formats a message as a JSON string for Cloud Logging."""
    log_entry = {
        "severity": severity,
        "message": message,
        **kwargs
    }
    print(json.dumps(log_entry))

# Get configuration from environment variables
GCP_PROJECT = os.environ.get("GCP_PROJECT")
MACHINE_TYPE = os.environ.get("MACHINE_TYPE", "g2-standard-8")
SOURCE_IMAGE_FAMILY = os.environ.get("SOURCE_IMAGE_FAMILY", "debian-11")
SOURCE_IMAGE_PROJECT = os.environ.get("SOURCE_IMAGE_PROJECT", "debian-cloud")

# Define the list of zones to try.
ZONES_TO_TRY = ["europe-west1-b","europe-west1-c","europe-west2-a","europe-west2-b","europe-west3-a","europe-west3-b","europe-west4-a","europe-west4-b","europe-west4-c","europe-west6-b","europe-west6-c"]

@app.route("/create/<int:instance_count>", methods=["POST"])
def create_instances(instance_count):
    """
    Trigger for creating a total number of GCE instances, spread across a 
    predefined list of zones. The process cycles through zones until the 
    total count is met.
    """
    if not GCP_PROJECT:
        log_structured("GCP_PROJECT environment variable not set.", severity="ERROR")
        return jsonify({"error": "GCP_PROJECT environment variable not set."}), 500
    
    if instance_count <= 0:
        log_structured(f"Received invalid instance count: {instance_count}", severity="WARNING")
        return jsonify({"error": "Instance count must be a positive integer."}), 400

    if not ZONES_TO_TRY:
        log_structured("Zone list is empty. No instances to create.", severity="WARNING")
        return jsonify({"message": "Zone list is empty. No instances to create."}), 200

    instances_client = compute_v1.InstancesClient()
    operations_client = compute_v1.ZoneOperationsClient()
    successfully_created_total = 0
    total_attempts = 0
    max_total_attempts = instance_count * len(ZONES_TO_TRY) * 3
    
    zone_cycler = cycle(ZONES_TO_TRY)
    created_instances_log = []

    log_structured(f"Goal: Create a total of {instance_count} instances across {len(ZONES_TO_TRY)} zones.", goal=instance_count, zones=ZONES_TO_TRY)

    while successfully_created_total < instance_count and total_attempts < max_total_attempts:
        total_attempts += 1
        zone = next(zone_cycler)

        try:
            instance_name = f"{MACHINE_TYPE.replace('_', '-')}-pool-{successfully_created_total}"
            
            instance_resource = {
                "name": instance_name,
                "machine_type": f"zones/{zone}/machineTypes/{MACHINE_TYPE}",
                "scheduling": {"on_host_maintenance": "TERMINATE"},
                "disks": [
                    {
                        "boot": True,
                        "auto_delete": True,
                        "initialize_params": {
                            "source_image": f"projects/{SOURCE_IMAGE_PROJECT}/global/images/family/{SOURCE_IMAGE_FAMILY}",
                            "disk_size_gb": "50",
                        },
                    }
                ],
                "network_interfaces": [
                    {"network": "global/networks/default", "access_configs": [{"type_": "ONE_TO_ONE_NAT"}]}
                ],
            }
            
            log_structured(f"Attempting to create instance #{successfully_created_total + 1} in {zone}", attempt=total_attempts, zone=zone)
            operation = instances_client.insert(
                project=GCP_PROJECT, zone=zone, instance_resource=instance_resource
            )

            # Wait for the operation to complete
            result = operations_client.wait(project=GCP_PROJECT, zone=zone, operation=operation.name, timeout=300)

            if result.error:
                error_message = result.error.errors[0].message
                raise google.api_core.exceptions.GoogleAPICallError(error_message)
            
            successfully_created_total += 1
            log_entry = f"Successfully created {instance_name} in {zone}."
            log_structured(log_entry, severity="INFO", instance_name=instance_name, zone=zone, total_created=successfully_created_total)
            created_instances_log.append(log_entry)

        except google.api_core.exceptions.GoogleAPICallError as e:
            log_structured(f"Attempt in {zone} failed: {e.message}. Trying next zone.", severity="WARNING", attempt=total_attempts, zone=zone, error=e.message)
            time.sleep(0.5)
        except Exception as e:
            log_structured(f"An unexpected error occurred in {zone}: {str(e)}. Trying next zone.", severity="ERROR", attempt=total_attempts, zone=zone, error=str(e))
            time.sleep(1)

    if successfully_created_total < instance_count:
        final_message = f"Process finished after {max_total_attempts} attempts. Failed to create the full count of instances."
        log_structured(final_message, severity="ERROR", total_created=successfully_created_total, goal=instance_count)
    else:
        final_message = "Successfully created all requested instances."
        log_structured(final_message, severity="INFO", total_created=successfully_created_total, goal=instance_count)
    
    return jsonify({
        "message": final_message,
        "total_requested": instance_count,
        "total_created": successfully_created_total,
        "log": created_instances_log
    }), 200


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
