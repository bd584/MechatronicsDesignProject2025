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


#Camera calibration completed on 17.11.25 

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Load the camera calibration values
camera_calibration = np.load('Sample_Calibration.npz')
CM=camera_calibration['CM'] #camera matrix
dist_coef=camera_calibration['dist_coef']# distortion coefficients from the camera

# Target ArUco IDs in required order
target_ids = list(range(1, 13))  # [1,2,...12]

current_target_index = 0
x_threshold = 2.0  # 1cm = aligned
alignment_start_time = None  # Track when alignment started
alignment_hold_duration = 3.0  # Hold for 3 seconds


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

    # If markers are detected
    if ids is not None:
        
        # Draw detected markers
        frame = aruco.drawDetectedMarkers(frame, corners, ids)

        # Estimate pose of each marker
        rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(corners, marker_size, CM, dist_coef)

        for i, (rvec, tvec) in enumerate(zip(rvecs, tvecs)):
            marker_id = ids[i][0]

            # Only care about the current target marker
            current_target_id = target_ids[current_target_index]

            if marker_id != current_target_id:
                continue  # skip all other markers

            # Extract X-distance from camera to marker (in cm)
            x_distance_cm = float(tvec[0][0])  # convert to float

            # Log X-distance
            logger.info(f"X-distance: {x_distance_cm:.2f}")
            
            # Draw axis for each marker
            frame = cv2.drawFrameAxes(frame, CM, dist_coef, rvec, tvec, 100)

            # Send movement command based on X-distance
            if x_distance_cm > x_threshold:
                message = "2"
                alignment_start_time = None  # Reset alignment timer if out of range
            elif x_distance_cm < -x_threshold:
                message = "1"
                alignment_start_time = None  # Reset alignment timer if out of range
            else:
                message = "0"  # Aligned
            sock.sendto(bytearray(message,'utf-8'), (UDP_IP, UDP_PORT)) # Send command via UDP

            # Check if alignment has been held for 3 seconds
            if alignment_start_time is not None and (time.time() - alignment_start_time) >= alignment_hold_duration:
                logger.info(f"Marker ID {current_target_id} held for {alignment_hold_duration} seconds. Moving to next target.")
                current_target_index += 1
                if current_target_index >= len(target_ids):
                    logger.info("All target markers aligned. Exiting.")
                    cap.release()
                    cv2.destroyAllWindows()
                    exit(0)

        # Add the frame rate to the image
        cv2.putText(frame, f"Target ID: {current_target_id} X={x_distance_cm:.1f}" , (10, 120 + 30*i), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 200, 255), 2,)
        
        cv2.putText(frame)
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