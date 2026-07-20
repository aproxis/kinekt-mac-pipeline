using UnityEngine;
using System.Collections.Generic;

// Чистый кольцевой буфер снапшотов — без собственного троттлинга.
// Частоту захвата регулирует ЕДИНСТВЕННЫЙ параметр: MaskCapture.captureInterval.
public class RingBuffer : MonoBehaviour
{
    [Tooltip("Сколько последних кадров маски хранить")]
    public int capacity = 16;

    private Queue<RenderTexture> buffer = new Queue<RenderTexture>();

    public int Count => buffer.Count;

    // i=0 — самый старый снапшот, i=Length-1 — самый новый
    public RenderTexture[] Snapshots => buffer.ToArray();

    public void Push(RenderTexture rt)
    {
        var copy = new RenderTexture(rt.width, rt.height, 0, rt.format);
        copy.Create();
        Graphics.Blit(rt, copy);

        buffer.Enqueue(copy);

        if (buffer.Count > capacity)
        {
            var oldest = buffer.Dequeue();
            if (oldest != null) oldest.Release();
        }
    }

    void OnDestroy()
    {
        while (buffer.Count > 0)
        {
            var rt = buffer.Dequeue();
            if (rt != null) rt.Release();
        }
    }
}
