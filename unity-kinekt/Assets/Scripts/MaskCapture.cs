using UnityEngine;
using Klak.Syphon;

[RequireComponent(typeof(RingBuffer))]
public class MaskCapture : MonoBehaviour
{
    public string serverName = "KinectMask";
    public Vector2Int captureSize = new Vector2Int(512, 512);

    [Tooltip("Единственный параметр частоты захвата в трейл: раз в N кадров (1 = каждый кадр)")]
    public int captureInterval = 3;
    public OutlineCompositor compositor;
    public bool flipHorizontal;
    public bool flipVertical;

    // Motion detection: уменьшенная копия маски для сравнения кадров
    private const int MotionSize = 32;
    private RenderTexture motionRT;
    private Texture2D motionTex;
    private Color32[] lastPixels;
    private bool hasLastPixels;

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

        motionRT = new RenderTexture(MotionSize, MotionSize, 0, RenderTextureFormat.R8);
        motionRT.Create();
        motionTex = new Texture2D(MotionSize, MotionSize, TextureFormat.R8, false);

        if (compositor != null)
            compositor.liveMaskTexture = downscaled;
    }

    void Update()
    {
        frameCount++;
        int interval = Mathf.Max(1, captureInterval); // защита от 0 — иначе деление на ноль
        if (frameCount % interval != 0) return;

        var source = client.Texture;
        if (source == null) return;

        // flip via blit scale/offset
        float sx = flipHorizontal ? -1 : 1;
        float sy = flipVertical ? -1 : 1;
        float ox = flipHorizontal ? 1 : 0;
        float oy = flipVertical ? 1 : 0;
        var scale = new Vector2(sx, sy);
        var offset = new Vector2(ox, oy);
        Graphics.Blit(source, downscaled, scale, offset);

        // Motion-режим: захватываем снепшот только если маска реально сдвинулась
        if (compositor != null &&
            compositor.StepMode == OutlineCompositor.ColorStepMode.Motion &&
            ComputeMotion() < compositor.motionThreshold)
        {
            return; // движения нет — трейл не растёт, цвет не шагает
        }

        Color color = compositor != null ? compositor.CurrentColor : Color.white;
        ring.Push(downscaled, color);
        if (compositor != null) compositor.NotifyCapture();
    }

    // RMS-разница текущей маски и предыдущего кадра (0..1).
    // Маленькая 32x32 текстура — быстрый readback, достаточно для порога движения.
    float ComputeMotion()
    {
        Graphics.Blit(downscaled, motionRT);

        var prevActive = RenderTexture.active;
        RenderTexture.active = motionRT;
        motionTex.ReadPixels(new Rect(0, 0, MotionSize, MotionSize), 0, 0);
        RenderTexture.active = prevActive;

        var px = motionTex.GetPixels32();
        if (!hasLastPixels)
        {
            lastPixels = px;
            hasLastPixels = true;
            return 0f;
        }

        long sum = 0;
        for (int i = 0; i < px.Length; i++)
        {
            int d = px[i].r - lastPixels[i].r;
            sum += d * d;
        }
        lastPixels = px;

        return Mathf.Sqrt((float)sum / px.Length) / 255f;
    }

    void OnDestroy()
    {
        if (downscaled != null) downscaled.Release();
        if (motionRT != null) motionRT.Release();
        if (motionTex != null) Destroy(motionTex);
    }
}
