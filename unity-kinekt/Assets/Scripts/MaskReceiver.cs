using UnityEngine;

[RequireComponent(typeof(RingBuffer))]
public class MaskReceiver : MonoBehaviour
{
    public string syphonServerName = "KinectMask";
    public Vector2Int captureSize = new Vector2Int(512, 512);
    public int captureInterval = 3;

    private RingBuffer ringBuffer;
    private RenderTexture captureRT;
    private System.IntPtr syphonClient;
    private int frameCount;

    void Start()
    {
        ringBuffer = GetComponent<RingBuffer>();
        captureRT = new RenderTexture(captureSize.x, captureSize.y, 0, RenderTextureFormat.R8);
        captureRT.Create();
    }

    void Update()
    {
        frameCount++;
        if (frameCount % captureInterval != 0) return;

        RenderTexture mask = SyphonManager.Instance.GetTexture(syphonServerName);
        if (mask == null) return;

        Graphics.Blit(mask, captureRT);
        ringBuffer.Push(captureRT);
    }

    void OnDestroy()
    {
        if (captureRT != null) captureRT.Release();
    }
}
