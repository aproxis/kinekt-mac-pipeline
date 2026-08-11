using UnityEngine;
using System.Collections.Generic;

// Снапшот маски + цвет, который у него был в момент захвата
// (нужно для "липких" цветов — каждый кадр навсегда хранит свой цвет)
public struct MaskFrame
{
    public RenderTexture texture;
    public Color color;
    public float capturedAt;
}

// Чистый кольцевой буфер снапшотов — без собственного троттлинга.
// Частоту захвата регулирует ЕДИНСТВЕННЫЙ параметр: MaskCapture.captureInterval.
public class RingBuffer : MonoBehaviour
{
    [Tooltip("Сколько последних кадров маски хранить")]
    public int capacity = 16;

    private Queue<MaskFrame> buffer = new Queue<MaskFrame>();

    public int Count => buffer.Count;

    // i=0 — самый старый снапшот, i=Length-1 — самый новый
    public MaskFrame[] Frames => buffer.ToArray();

    // совместимость со старым кодом: только текстуры
    public RenderTexture[] Snapshots
    {
        get
        {
            var frames = buffer.ToArray();
            var tex = new RenderTexture[frames.Length];
            for (int i = 0; i < frames.Length; i++) tex[i] = frames[i].texture;
            return tex;
        }
    }

    public void Push(RenderTexture rt, Color color)
    {
        var copy = new RenderTexture(rt.width, rt.height, 0, rt.format);
        copy.Create();
        Graphics.Blit(rt, copy);

        buffer.Enqueue(new MaskFrame { texture = copy, color = color, capturedAt = Time.time });

        if (buffer.Count > capacity)
        {
            var oldest = buffer.Dequeue();
            if (oldest.texture != null) oldest.texture.Release();
        }
    }

    void OnDestroy()
    {
        while (buffer.Count > 0)
        {
            var f = buffer.Dequeue();
            if (f.texture != null) f.texture.Release();
        }
    }
}
