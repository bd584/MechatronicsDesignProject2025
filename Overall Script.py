# This script is the overall script used for the ganrty project for Mechatronics Design Project 2025.
# It captures video from the camera, detects ArUco markers, estimates their position, and communicates with raspberry pi over TCP/UDP the direction
# needed to move to align with the target. Once aligned with a marker, it moves to the next target marker in sequence.
import cv2
import cv2.aruco as aruco
import numpy as np
import time # To ensure a steady processing rate
import logging 
import socket  # For UDP communication

# UDP configuration
UDP_IP = "138.38.229.217"  # Replace with your Raspberry Pi's IP address
UDP_PORT = 50002  # Port to send messages to
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Create UDP socket

# UDP message commands
MOVE_Start = "1"
MOVE_Forward = "2"
MOVE_Backward = "3"
MOVE_Stop = "4"

#Camera calibration completed on 17.11.25 

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Load the camera calibration values
camera_calibration = np.load('Sample_Calibration.npz')
CM=camera_calibration['CM'] #camera matrix
dist_coef=camera_calibration['dist_coef']# distortion coefficients from the camera

# Maximum ID allowed for user entry (this project uses markers 1..12)
MAX_AREUCO_ID = 7

# Ask the user which ArUco targets (IDs) they want to visit, in order
def get_user_targets(max_id=MAX_AREUCO_ID):
    while True:
        try:
            num = int(input(f"Welcome Fellow Alien! How many cows would you like to abduct today? Enter the number of targets to hit (1-{max_id}): "))
            if 1 <= num <= max_id:
                break
            print(f"Please enter a number between 1 and {max_id}.")
        except ValueError:
            print("Invalid input. Enter an integer.")

    targets = []
    for i in range(num):
        while True:
            try:
                entry = int(input(f"Enter cow #{i+1} (1-{max_id}): "))
                if not (1 <= entry <= max_id):
                    print(f"Not on the menu! Cows must be between 1 and {max_id} (inclusive).")
                    continue
                if entry in targets:
                    print("You already entered that Cow. Please choose a different one.")
                    continue
                targets.append(entry)
                break
            except ValueError:
                print("Invalid input. Enter an integer.")
    return targets

# Target ArUco IDs in order the user wants to visit
target_ids = get_user_targets()
logger.info(f"Cow targetting sequence set by Alien: {target_ids}, please bare with us while we jump to hyperspace, then proceed with the abduction!")

current_target_index = 0
x_threshold = 10 # 1cm = aligned
x_offset = -49.0  # Offset to be added to X-distance for calibration
alignment_start_time = None  # Track when alignment started
alignment_hold_duration = 3.0  # Hold for 2 seconds


# Define the ArUco dictionary and parameters
marker_size = 45
aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
parameters = aruco.DetectorParameters()

# Define a processing rate
processing_period = 0.25

# Create a window showing the frame
cv2.namedWindow("Frame", cv2.WINDOW_AUTOSIZE)


# Start capturing video
cap = cv2.VideoCapture(0)

# Set the starting time
start_time = time.time()
fps = 0

#USER INTERFACE SCRIPT THAT ENDS WITH THE START COMMAND BEING SENT

sock.sendto(bytes(MOVE_Start, 'utf-8'), (UDP_IP, UDP_PORT))

while True:
    # Capture frame-by-frame
    ret, frame = cap.read()
    if not ret:
        print("Can't receive frame (stream end?). Exiting ...")
        break

    # Convert frame to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detect markers
    corners, ids, rejectedImgPoints = aruco.detectMarkers(gray, aruco_dict, parameters=parameters)
    
    # Top-level handling for when nothing is detected or the current target isn't present
    # Work out the current target ID here (used in both display and checks)
    current_target_id = target_ids[current_target_index]

    # If no markers are detected at all -> Move backwards and skip pose processing
    if ids is None:
        sock.sendto(bytes(MOVE_Backward, 'utf-8'), (UDP_IP, UDP_PORT))
        x_distance_mm = float('nan')   # Default for display
        i = 0
        # Draw nothing or leave frame as-is; skip pose estimation
    else:
        # Convert ids to a flattened python list for membership check
        ids_list = ids.flatten().tolist()

        # If the current target isn't present in the detected IDs -> Move backwards
        if current_target_id not in ids_list:
            sock.sendto(bytes(MOVE_Backward, 'utf-8'), (UDP_IP, UDP_PORT))
            x_distance_mm = float('nan')   # Default for display
            i = 0
            # Still draw detected markers to inform debugging
            frame = aruco.drawDetectedMarkers(frame, corners, ids)
        else:
            # Target is present -> draw markers and estimate pose of all detected markers
            frame = aruco.drawDetectedMarkers(frame, corners, ids)
            rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(corners, marker_size, CM, dist_coef)

            x_distance_mm = float('nan')   # Default when not detected

            for i, (rvec, tvec) in enumerate(zip(rvecs, tvecs)):
                marker_id = ids[i][0]

                # Only care about the current target marker
                if marker_id != current_target_id:
                    continue  # skip all other markers

                # Extract X-distance from camera to marker (in mm)
                x_distance_mm = float(tvec[0][0])

            # Log X-distance
            logger.info(f"X-distance: {x_distance_mm:.2f} mm")
            
            # Draw axis for each marker
            #frame = cv2.drawFrameAxes(frame, CM, dist_coef, rvec, tvec, 100)

            # Send movement command based on X-distance
            if x_distance_mm > x_threshold + x_offset:
                message = MOVE_Forward
                alignment_start_time = None  # Reset alignment timer if out of range
            elif x_distance_mm < -x_threshold + x_offset:
                message = MOVE_Backward
                alignment_start_time = None  # Reset alignment timer if out of range
            else:
                message = MOVE_Stop  # Aligned
                # Start alignement timer
                if alignment_start_time is None:
                    alignment_start_time = time.time()  # Start timing alignment
                    logger.info(f"Abduction in progress on cow #{current_target_id}. Holding for {alignment_hold_duration} seconds...")

            sock.sendto(bytes(message, 'utf-8'), (UDP_IP, UDP_PORT)) # Send command via UDP

            # Check if alignment has been held for 3 seconds
            if alignment_start_time is not None and (time.time() - alignment_start_time) >= alignment_hold_duration:
                logger.info(f"Abduction complete on cow #{current_target_id} held for {alignment_hold_duration} seconds. Targeting next cow.")
                current_target_index += 1
                # Print and log the next target ID (if any) so the user can see it immediately
                if current_target_index < len(target_ids):
                    next_target_id = target_ids[current_target_index]
                    logger.info(f"Switching to next target ID: {next_target_id}")
                    print(f"Switching to next cow: {next_target_id}")
                if current_target_index >= len(target_ids):
                    logger.info("All cows abducted. Exiting.")
                    cap.release()
                    cv2.destroyAllWindows()
                    exit(0)

        # Add the frame rate to the image
        cv2.putText(frame, f"Cow Number: {current_target_id} 4X={x_distance_mm - x_offset:.1f} mm" , (10, 120 + 30*i), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 200, 255), 2,)
        cv2.putText(frame, f"CAMERA FPS: {fps:.2f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, f"PROCESSING FPS: {1/processing_period:.2f}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    
        
    # Display the resulting frame
    cv2.imshow('Frame', frame)

    # Break the loop on 'q' key press
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

    # Ensure a steady processing rate
    elapsed_time = time.time() - start_time
    fps = 1 / elapsed_time
    if elapsed_time < processing_period:
        time.sleep(processing_period - elapsed_time)
    start_time = time.time()


# When everything is done, release the capture and close windows
cap.release()
cv2.destroyAllWindows()