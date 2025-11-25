# This Script aims to connect to the camera and identify Aruco Markers and calculate the distance
# the camera is from the marker using pose estimation.
# It uses the camera calibration values to estimate the pose of the markers.
import cv2
import cv2.aruco as aruco
import numpy as np
import time # To ensure a steady processing rate
import logging 

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
x_threshold = 1.0   # 1cm = aligned

# Define the ArUco dictionary and parameters
marker_size = 45
aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
parameters = aruco.DetectorParameters()

# Define a processing rate
processing_period = 0.25

# Create two OpenCV named windows
cv2.namedWindow("Frame", cv2.WINDOW_AUTOSIZE)
#cv2.namedWindow("Gray", cv2.WINDOW_AUTOSIZE)

# Position the windows next to each other
#cv2.moveWindow("Gray", 640, 100)
cv2.moveWindow("Frame", 0, 100)
# Start capturing video
cap = cv2.VideoCapture(0)

# Set the starting time
start_time = time.time()
fps = 0

#target timer if needed to skip
target_missing_start = None           
target_missing_timeout = 5.0 

while True:
    # Capture frame-by-frame
    ret, frame = cap.read()
    if not ret:
        print("Can't receive frame (stream end?). Exiting ...")
        break

    # Convert frame to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    #cv2.imshow('gray-image', gray)

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
            

            # Log marker ID and transformation matrix (tvec)
            logger.info(f"Marker ID: {current_target_id}, tvec: {tvec.flatten()}, rvec: {rvec.flatten()}, X-distance: {x_distance_cm:.2f}")
            
            # Draw axis for each marker
            frame = cv2.drawFrameAxes(frame, CM, dist_coef, rvec, tvec, 100)

            # Check alignment
            if abs(x_distance_cm) <= x_threshold:
                logger.info(f"Marker ID {current_target_id} aligned (X-distance: {x_distance_cm:.2f} cm). Moving to next target.")
                current_target_index += 1
                if current_target_index >= len(target_ids):
                    logger.info("All target markers aligned. Exiting.")
                    cap.release()
                    cv2.destroyAllWindows()
                    exit(0)

    # Add the frame rate to the image
    cv2.putText(frame, f"Target ID: {current_target_id} X={x_distance_cm:.1f}" , (10, 120 + 30*i), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 200, 255), 2,)
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