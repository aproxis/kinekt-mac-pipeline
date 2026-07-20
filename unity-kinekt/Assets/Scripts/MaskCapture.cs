using UnityEngine;
using Klak.Syphon;

[RequireComponent(typeof(RingBuffer))]
public class MaskCapture : MonoBehaviour
{
    public string serverName = "KinectMask";
    public Vector2Int captureSize = new Vector2Int(512, 512);
    public int captureInterval = 3;
    public OutlineCompositor compositor;

    private RingBuffer ring;
    private SyphonClient client;
    private RenderTexture downscaled;
    private int frameCount;

    void Start()
    {
        ring = GetComponent<RingBuffer>();
        client = gameObject.AddComponent<SyphonClient>();
        client.ServerName = serverName.StartsWith("/") ? serverName : "/" + serverName;

        downscaled = new RenderTexture(captureSize.x, captureSize.y, 0, RenderTextureFormat.R8);
        downscaled.Create();

        if (compositor != null)
            compositor.liveMaskTexture = downscaled;
    }

    void Update()
    {
        frameCount++;
        if (frameCount % captureInterval != 0) return;

        var source = client.Texture;
        if (source == null) return;

        Graphics.Blit(source, downscaled);
        ring.Push(downscaled);
    }

    void OnDestroy()
    {
        if (downscaled != null) downscaled.Release();
    }
}
