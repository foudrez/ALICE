import cv2

def test_cameras():
    print("Scanning for video sources...")
    for i in range(3): # Check the first 5 slots
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                print(f"✅ Camera Index {i} is ACTIVE and sending frames.")
                # Show the feed in a tiny window so you can visually confirm it's VSeeFace
                cv2.imshow(f"Camera {i}", cv2.resize(frame, (400, 300)))
        cap.release()
    
    print("Press any key on the video windows to close...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    test_cameras()