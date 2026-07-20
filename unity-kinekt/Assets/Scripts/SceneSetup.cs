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

        GUILayout.BeginArea(new Rect(10, 10, 400, 100));
        GUILayout.Label("Kinekt360 — Outline Effect");
        GUILayout.Label($"Camera: {(cam != null ? "OK" : "MISSING")}");
        GUILayout.Label($"MaskCapture: {(comp != null ? "OK" : "MISSING — add to Camera")}");
        GUILayout.Label($"SyphonClient: {(syphon != null ? "OK" : "MISSING — added by MaskCapture")}");
        GUILayout.Label($"Syphon Texture: {(syphon != null && syphon.Texture != null ? "RECEIVING" : "waiting for Python...")}");
        GUILayout.EndArea();
    }
}
