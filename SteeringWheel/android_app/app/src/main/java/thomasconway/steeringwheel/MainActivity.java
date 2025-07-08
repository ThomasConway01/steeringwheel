package thomasconway.steeringwheel;

import java.nio.ByteBuffer;

import java.net.InetSocketAddress;
import java.net.SocketTimeoutException;
import androidx.appcompat.app.AppCompatActivity;

import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.os.Bundle;
import android.util.Log;
import android.view.MotionEvent;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;

import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.net.Socket;

public class MainActivity extends AppCompatActivity implements SensorEventListener {

    private static final String TAG = "MainActivity";
    private static final String HOST = "192.168.1.29"; // Your PC's IP address
    private static final int PORT = 65433;
    private boolean isConnected = false;
    private TextView textViewStatus;

    private Button buttonForward;
    private Button buttonBrake;
    private TextView textViewSpeed;
    private Button buttonCalibrate;

    private SensorManager sensorManager;
    private Sensor gyroscopeSensor;

    private float rotationX = 0;
    private float rotationY = 0;
    private boolean brakePressed = false;
    private boolean acceleratePressed = false;

    private Socket socket;
    private DataOutputStream outputStream;
    private DataInputStream inputStream;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        buttonForward = findViewById(R.id.buttonForward);
        buttonBrake = findViewById(R.id.buttonBrake);
        textViewSpeed = findViewById(R.id.textViewSpeed);
        buttonCalibrate = findViewById(R.id.buttonCalibrate);
        textViewStatus = findViewById(R.id.textViewStatus);

        sensorManager = (SensorManager) getSystemService(SENSOR_SERVICE);
        gyroscopeSensor = sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE);
buttonForward.setOnTouchListener(new View.OnTouchListener() {
    @Override
    public boolean onTouch(View v, MotionEvent event) {
        acceleratePressed = event.getAction() == MotionEvent.ACTION_DOWN;
        return false;
    }
});

buttonBrake.setOnTouchListener(new View.OnTouchListener() {
    @Override
    public boolean onTouch(View v, MotionEvent event) {
        brakePressed = event.getAction() == MotionEvent.ACTION_DOWN;
        return false;
    }
});


        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    try {
                        socket = new Socket();
                        socket.connect(new InetSocketAddress(HOST, PORT), 5000); // 5 second timeout
                        outputStream = new DataOutputStream(socket.getOutputStream());
                        inputStream = new DataInputStream(socket.getInputStream());
                        isConnected = true;
                        runOnUiThread(() -> textViewStatus.setText("Connected"));
                    } catch (SocketTimeoutException e) {
                        runOnUiThread(() -> textViewStatus.setText("Timeout: Check PC IP/Port"));
                        Log.e(TAG, "Connection timeout: " + e.getMessage());
                        return;
                    } catch (Exception e) {
                        runOnUiThread(() -> textViewStatus.setText("Failed: " + e.getClass().getSimpleName()));
                        Log.e(TAG, "Connection error: " + e.getMessage());
                        return;
                    }

                    while (isConnected) {
                        try {
                            // Send data to PC
                            // Always send command character first
                            if (brakePressed) {
                                outputStream.writeChar('s');
                            } else if (acceleratePressed) {
                                outputStream.writeChar('w');
                            } else {
                                outputStream.writeChar('n');
                            }
                            // Always follow with steering data
                            outputStream.writeFloat(rotationX);
                            outputStream.writeFloat(rotationY);
                            outputStream.flush();
                            // Debug log the exact bytes being sent
                            byte[] sentBytes = new byte[9];
                            sentBytes[0] = (byte)(brakePressed ? 's' : acceleratePressed ? 'w' : 'n');
                            System.arraycopy(floatToByteArray(rotationX), 0, sentBytes, 1, 4);
                            System.arraycopy(floatToByteArray(rotationY), 0, sentBytes, 5, 4);
                            Log.d(TAG, "Sent bytes: " + bytesToHex(sentBytes) +
                                  " (" + (brakePressed ? "BRAKE" : acceleratePressed ? "ACCEL" : "NEUTRAL") +
                                  " X=" + rotationX + " Y=" + rotationY + ")");

                            Thread.sleep(20); // Increased delay for more stable transmission
                        } catch (Exception e) {
                            Log.e(TAG, "Error in data loop: " + e.getMessage());
                            isConnected = false;
                            runOnUiThread(() -> textViewStatus.setText("Disconnected"));
                            break;  // Exit loop on error
                        }
                    }

                } catch (Exception e) {
                    Log.e(TAG, "Error: " + e.getMessage());
                } finally {
                    try {
                        if (socket != null) {
                            socket.close();
                        }
                    } catch (IOException e) {
                        Log.e(TAG, "Error closing socket: " + e.getMessage());
                    }
                }
            }
        }).start();
    }

    @Override
    protected void onResume() {
        super.onResume();
        sensorManager.registerListener(this, gyroscopeSensor, SensorManager.SENSOR_DELAY_GAME);
    }

    @Override
    protected void onPause() {
        super.onPause();
        sensorManager.unregisterListener(this);
    }

    @Override
    public void onSensorChanged(SensorEvent event) {
        if (event.sensor.getType() == Sensor.TYPE_GYROSCOPE) {
            // Send raw gyro values with sensitivity scaling
            rotationX = event.values[0] * 2.5f; // Reduced scaling for smoother control
            rotationY = event.values[1] * 2.5f;
            
            // Dynamic deadzone based on current speed/state
            float deadzone = 0.3f;
            if (Math.abs(rotationX) < deadzone) rotationX = 0;
            if (Math.abs(rotationY) < deadzone) rotationY = 0;
            
            Log.d(TAG, "Raw gyro data: rotationX=" + rotationX + ", rotationY=" + rotationY);
        }
    }

    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) {
    }

    private static byte[] floatToByteArray(float value) {
        return ByteBuffer.allocate(4).putFloat(value).array();
    }

    private static String bytesToHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder();
        for (byte b : bytes) {
            sb.append(String.format("%02X ", b));
        }
        return sb.toString().trim();
    }
}