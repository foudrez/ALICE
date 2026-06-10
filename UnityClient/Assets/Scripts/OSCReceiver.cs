using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Collections.Concurrent;
using UnityEngine;

public class OSCReceiver : MonoBehaviour
{
    public int listenPort = 9000;
    private UdpClient udpClient;
    private Thread listenerThread;
    private bool isRunning;
    
    // Thread-safe queue for main thread execution
    private ConcurrentQueue<Action> mainThreadActions = new ConcurrentQueue<Action>();
    
    public VRMController vrmController;

    void Start()
    {
        udpClient = new UdpClient(listenPort);
        isRunning = true;
        listenerThread = new Thread(ListenForOSC);
        listenerThread.IsBackground = true;
        listenerThread.Start();
        Debug.Log($"OSC Receiver started on port {listenPort}");
    }

    void Update()
    {
        // Execute queued actions on main thread
        while (mainThreadActions.TryDequeue(out Action action))
        {
            action?.Invoke();
        }
    }

    private void ListenForOSC()
    {
        IPEndPoint remoteEndPoint = new IPEndPoint(IPAddress.Any, 0);

        while (isRunning)
        {
            try
            {
                byte[] data = udpClient.Receive(ref remoteEndPoint);
                ParseOSCMessage(data);
            }
            catch (SocketException e)
            {
                if (isRunning) Debug.LogError($"Socket Exception: {e}");
            }
        }
    }

    private void ParseOSCMessage(byte[] data)
    {
        try
        {
            // A highly simplified OSC parser assuming python-osc structure:
            // Address pattern (null terminated) padded to 4 bytes
            // Type tags (",s" etc.) (null terminated) padded to 4 bytes
            // Arguments padded to 4 bytes
            
            int index = 0;
            string address = ReadString(data, ref index);
            string typeTags = ReadString(data, ref index);
            
            if (typeTags.Length > 1 && typeTags[1] == 's') // Extract string argument
            {
                string argument = ReadString(data, ref index);
                
                mainThreadActions.Enqueue(() => {
                    HandleMessage(address, argument);
                });
            }
        }
        catch (Exception ex)
        {
            Debug.LogError($"Error parsing OSC: {ex.Message}");
        }
    }

    private string ReadString(byte[] data, ref int index)
    {
        int start = index;
        while (index < data.Length && data[index] != 0)
        {
            index++;
        }
        string result = Encoding.UTF8.GetString(data, start, index - start);
        
        // Skip nulls and pad to 4 bytes
        index++; 
        int padding = 4 - (index % 4);
        if (padding < 4) index += padding;
        
        return result;
    }

    private void HandleMessage(string address, string argument)
    {
        if (vrmController == null) return;
        
        Debug.Log($"OSC: {address} -> {argument}");
        
        switch (address)
        {
            case "/avatar/emotion":
            case "/avatar/animation":
                vrmController.SetEmotion(argument);
                break;
            case "/avatar/speech":
                // Optional: show a subtitle bubble
                break;
            case "/avatar/status":
                // Optional: show status UI
                break;
        }
    }

    void OnDestroy()
    {
        isRunning = false;
        if (udpClient != null)
        {
            udpClient.Close();
        }
        if (listenerThread != null && listenerThread.IsAlive)
        {
            listenerThread.Abort();
        }
    }
}
