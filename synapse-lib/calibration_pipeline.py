from time import time
import numpy as np
import cv2

if __name__ == "__main__":
    # Chessboard dimensions (internal corners)
    CHECKERBOARD = (9, 6)  # Number of internal corners per row and column

    # Criteria for corner subpixel accuracy
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    square_size = 20  # mm

    # Prepare object points (0, 0, 0), (1, 0, 0), (2, 0, 0), ..., (8, 5, 0)
    objp = np.zeros((CHECKERBOARD[0] * CHECKERBOARD[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0 : CHECKERBOARD[0], 0 : CHECKERBOARD[1]].T.reshape(-1, 2)
    objp *= square_size

    # Arrays to store object points and image points from all frames
    objpoints = []  # 3D points in real-world space
    imgpoints = []  # 2D points in image plane

    # Start capturing from the webcam (0 is the default camera)
    cap = cv2.VideoCapture(0)

    # Initialize a counter for the number of valid frames
    frame_count = 0
    max_frames = 40  # Number of frames to capture (you can adjust this number)

    while True:
        ret, frame = cap.read()

        if not ret:
            print("Failed to grab frame")
            break

        # Convert the frame to grayscale for better corner detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Find the chessboard corners
        ret, corners = cv2.findChessboardCorners(gray, CHECKERBOARD, None)

        if ret:
            # Refine the corner positions for better accuracy
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

            # Add the object points and image points
            objpoints.append(objp)
            imgpoints.append(corners2)

            # Draw and display the corners on the frame
            cv2.drawChessboardCorners(frame, CHECKERBOARD, corners2, ret)

            # Increment the frame count for successful corner detection
            frame_count += 1
            print(f"Frame {frame_count} captured.")

        # Display the frame with the detected chessboard corners
        # cv2.imshow("Chessboard Detection", frame)

        # Exit the loop when 'q' is pressed
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

        # Perform calibration after enough frames have been captured
        if frame_count >= max_frames:
            cap.release()

            print(f"Calibration process complete with {frame_count} frames.")
            start_time = time()
            ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
                objectPoints=objpoints,
                imagePoints=imgpoints,
                imageSize=gray.shape[::-1],
                cameraMatrix=None,  # pyright: ignore
                distCoeffs=None,  # pyright: ignore
            )  # Optional flags
            end_time = time()
            undistorted_frame = cv2.undistort(frame, mtx, dist)
            # cv2.imshow("Undistorted Image", undistorted_frame)
            if ret:
                print(
                    f"Camera calibration successful in {end_time - start_time} (seconds)!"
                )
                print("Camera matrix (fx, fy, cx, cy):\n", mtx)
                print("Dist Coeffs: ", dist)
            else:
                print("Calibration failed.")
            break

    # Release the camera and close the OpenCV windows
    cap.release()
    cv2.destroyAllWindows()
