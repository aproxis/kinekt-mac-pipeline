using UnityEngine;

public class SyphonReceiver : MonoBehaviour
{
    [Tooltip("Имя Syphon сервера из Python скрипта")]
    public string serverName = "KinectMask";
    public RenderTexture targetTexture;

    private System.IntPtr _client;

    void Start()
    {
        if (targetTexture == null)
        {
            targetTexture = new RenderTexture(512, 512, 0);
            targetTexture.Create();
        }
    }

    void Update()
    {
        ReceiveFrame();
    }

    void ReceiveFrame()
    {
        if (_client == System.IntPtr.Zero)
        {
            string name = serverName;
            string appName = Application.productName;
            _client = SyphonPlugin.CreateReceiver(appName, name);
        }
        if (_client != System.IntPtr.Zero)
        {
            SyphonPlugin.ReceiveFrame(_client, targetTexture.GetNativeTexturePtr());
        }
    }

    void OnDestroy()
    {
        if (_client != System.IntPtr.Zero)
        {
            SyphonPlugin.DestroyReceiver(_client);
            _client = System.IntPtr.Zero;
        }
    }
}
