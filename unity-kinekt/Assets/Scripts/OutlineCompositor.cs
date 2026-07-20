using UnityEngine;

[RequireComponent(typeof(RingBuffer))]
public class OutlineCompositor : MonoBehaviour
{
    [Header("Outline")]
    public Color outlineColor = Color.cyan;
    [Range(1, 10)] public float outlineWidth = 3;
    [Range(0, 3)] public float fadePower = 1.5f;

    [Header("Drift")]
    [Range(0, 0.2f)] public float driftAmount = 0.02f;

    [Header("Hue")]
    [Range(0, 1)] public float hueShift = 0.3f;

    [Header("Performance")]
    public int snapshotCapacity = 16;
    public int captureStride = 3;

    [Header("Live Feed")]
    public RenderTexture liveMaskTexture;

    private RingBuffer ringBuffer;
    private Material outlineMat;
    private RenderTexture compositeRT;

    void Start()
    {
        ringBuffer = GetComponent<RingBuffer>();
        ringBuffer.capacity = snapshotCapacity;
        ringBuffer.stride = captureStride;

        outlineMat = new Material(Shader.Find("Kinekt/OutlineComposite"));
    }

    void Update()
    {
        if (liveMaskTexture == null) return;

        int w = liveMaskTexture.width;
        int h = liveMaskTexture.height;

        if (compositeRT == null || compositeRT.width != w || compositeRT.height != h)
        {
            if (compositeRT != null) compositeRT.Release();
            compositeRT = new RenderTexture(w, h, 0, RenderTextureFormat.ARGB32);
            compositeRT.Create();
        }

        RenderTexture.active = compositeRT;
        GL.Clear(false, true, Color.clear);
        RenderTexture.active = null;

        Graphics.Blit(liveMaskTexture, compositeRT);

        var snapshots = ringBuffer.Snapshots;
        for (int i = 0; i < snapshots.Length; i++)
        {
            if (snapshots[i] == null) continue;

            float age = (float)i / Mathf.Max(snapshots.Length - 1, 1);
            outlineMat.SetTexture("_MainTex", snapshots[i]);
            outlineMat.SetColor("_OutlineColor", outlineColor);
            outlineMat.SetFloat("_OutlineWidth", outlineWidth);
            outlineMat.SetFloat("_FadePower", fadePower);
            outlineMat.SetFloat("_DriftAmount", driftAmount);
            outlineMat.SetFloat("_HueShift", hueShift);
            outlineMat.SetFloat("_Age", age);
            outlineMat.SetFloat("_SnapshotAlpha", 1.0f);

            Graphics.Blit(snapshots[i], compositeRT, outlineMat);
        }
    }

    void OnGUI()
    {
        if (compositeRT != null)
            Graphics.DrawTexture(new Rect(0, 0, Screen.width, Screen.height), compositeRT);
    }

    void OnDestroy()
    {
        if (outlineMat != null) Destroy(outlineMat);
        if (compositeRT != null) compositeRT.Release();
    }
}
