using UnityEngine;
using System.Collections.Generic;

public class RingBuffer : MonoBehaviour
{
    [Tooltip("Сколько последних кадров маски хранить")]
    public int capacity = 16;

    [Tooltip("Брать каждый N-й кадр (1 = каждый)")]
    public int stride = 3;

    private Queue<RenderTexture> buffer = new Queue<RenderTexture>();
    private int frameCount;

    public int Count => buffer.Count;
    public RenderTexture[] Snapshots => buffer.ToArray();

    public void Push(RenderTexture rt)
    {
        frameCount++;
        if (frameCount % stride != 0) return;

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
