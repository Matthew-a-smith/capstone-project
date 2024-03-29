import json
import pandas as pd
import tensorflow as tf
import os
import subprocess
import csv

#########################
#### HTTP MODEL      ####
#########################

def run_tshark_command(pcap_file):
    tshark_cmd = [
        "tshark",
        "-r", pcap_file,  # Specify the input pcap file
        "-Y", "tcp",      # Filter for TCP traffic
        "-E", "header=y",  # Add header to output
        "-T", "fields",  # Output fields
        "-E", "separator=,",  # CSV separator
        "-e", "frame.time",  # Add frame time
        "-e", "ip.dst",
        "-e", "ip.src",
        "-e", "tcp.dstport",
        "-e", "tcp.srcport",
        "-e", "tcp.window_size_value",
        "-e", "tcp.flags",
    ]
    # Capture TCP traffic using subprocess
    process = subprocess.Popen(tshark_cmd, stdout=subprocess.PIPE, universal_newlines=True)
    return process

def process_pcap_to_csv3(pcap_file):
    process = run_tshark_command(pcap_file)

    csv_filename = pcap_file.split('.')[0] + ".csv"
    with open(csv_filename, "w", newline="") as csvfile:
        fieldnames = ["date", "time", "ip.dst", "ip.src", "tcp.dstport", "tcp.srcport", "tcp.window_size_value", "tcp.flags"]  # Define CSV header field names
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        # Write CSV header
        writer.writeheader()

        # Skip the first line containing the field names
        next(process.stdout)
                
        for line in process.stdout:
            fields = line.strip().split(',')
            date_str = fields[0]
            time_str = fields[1]
            row = {"date": fields[0],"time": fields[1], "ip.dst": fields[2], "ip.src": fields[3], "tcp.dstport": fields[4], "tcp.srcport": fields[5], "tcp.window_size_value": fields[6], "tcp.flags": fields[7]}
            writer.writerow(row)
            csvfile.flush()  # Flush the buffer to ensure data is written to the file

    process.terminate()

    print("PCAP to CSV conversion completed.")

    # Load the inference model
    ICMP_inference_model = "Models/Inferance/http-traffic.keras"
    loaded_model = tf.keras.models.load_model(ICMP_inference_model)

    # Function to make prediction on the entire dataset
    def make_predictions(data):
        input_data = {name: tf.convert_to_tensor(data[name].values.reshape(-1, 1)) for name in data.columns if name not in ['ip.src', 'ip.dst']}
        predictions = loaded_model.predict(input_data)
        return predictions.flatten()

    # Load data from CSV file
    data = pd.read_csv(csv_filename)

    # Make predictions for the entire dataset
    all_predictions = make_predictions(data)

    # Set thresholds for writing to JSON
    write_threshold = 0.95

    # Prepare output data for predictions above threshold
    output_data = []
    for index, prediction in enumerate(all_predictions):
        if prediction > write_threshold:
            output_data.append({"Index": index, "Prediction": prediction * 100, "Details": data.iloc[index].to_dict()})
        
    # Write predictions with additional information to a JSON file
    predictions_filename = pcap_file.split('.')[0] + "http--predictions.json"
    with open(predictions_filename, 'w') as f:
        json.dump(output_data, f, indent=4)

    print("Predictions above the threshold have been written to", predictions_filename)

    return csv_filename, predictions_filename

def get_top_predictions3(predictions_file, top_n=10):
    with open(predictions_file) as f:
        predictions_data = json.load(f)
    
    top_predictions = predictions_data[:top_n]
    return top_predictions