using UnityEngine;

[ExecuteAlways]
public class SceneSetup : MonoBehaviour
{
    void OnGUI()
    {
        var cam = Camera.main;
        if (cam == null) return;

        var comp = cam.GetComponent<MaskCapture>();
        var syphon = cam.GetComponent<Klak.Syphon.SyphonClient>();
        bool hasTex = syphon != null && syphon.Texture != null;

        GUILayout.BeginArea(new Rect(10, 10, 500, 140));
        GUILayout.Label("Kinekt360 — Outline Effect");
        GUILayout.Label($"Camera: {(cam != null ? "OK" : "MISSING")}");
        GUILayout.Label($"MaskCapture: {(comp != null ? "OK" : "MISSING — add to Camera")}");
        GUILayout.Label($"SyphonClient: {(syphon != null ? "OK" : "MISSING — added by MaskCapture")}");
        GUILayout.Label(hasTex
            ? $"Syphon Texture: RECEIVING {syphon.Texture.width}x{syphon.Texture.height}"
            : "Syphon Texture: waiting for Python...");
        GUILayout.EndArea();

        // сырое превью Syphon-текстуры В ОБХОД OutlineCompositor —
        // если тут видно силуэт, проблема дальше по цепочке (компоновщик/шейдер)
        if (hasTex)
        {
            GUI.DrawTexture(new Rect(10, 160, 300, 300), syphon.Texture, ScaleMode.ScaleToFit, false);
        }
    }
}
