using UnityEngine;

// Опциональный компонент. Добавь его на тот же GameObject, что и OutlineCompositor —
// он автоматически заменит линейный дрифт трейла на круговое движение.
// Убери компонент (или отключи), чтобы вернуться к обычному линейному дрифту.
//
// Так как исходная картинка плоская (силуэт из depth-маски), реального 3D-вращения
// нет — вместо этого имитируем его:
//   - копии смещаются по окружности (sin/cos от угла)
//   - при повороте "боком" (угол ~90°/270°) силуэт сжимается по X — fake-перспектива
//   - при повороте "спиной" (угол ~180°) копия темнее/прозрачнее — fake-затенение
//   - порядок отрисовки пересчитывается каждый кадр, чтобы ближние копии
//     перекрывали дальние, как в настоящей карусели
[RequireComponent(typeof(OutlineCompositor))]
public class TrailCarousel : MonoBehaviour, ITrailMotion
{
    [Header("Orbit")]
    [Tooltip("Радиус орбиты в UV-единицах (0.15 = 15% ширины кадра)")]
    [Range(0, 0.5f)] public float radius = 0.15f;

    [Tooltip("Сколько полных оборотов укладывается во весь трейл (age 0..1)")]
    [Range(0.1f, 3f)] public float turns = 1f;

    [Tooltip("Угол живого кадра (age=0), градусы")]
    public float startAngleDeg = 0f;

    [Header("Fake Depth")]
    [Tooltip("Насколько сильно сжимается силуэт по X при повороте боком (0 = без искажения, 1 = полное сплющивание)")]
    [Range(0, 1)] public float foreshorten = 0.6f;

    [Tooltip("Насколько темнее/прозрачнее копия, когда она \"дальше\" от зрителя")]
    [Range(0, 1)] public float depthDim = 0.5f;

    [Tooltip("Лёгкое вертикальное покачивание в такт вращению")]
    [Range(0, 0.2f)] public float verticalWobble = 0.03f;

    [Tooltip("Отражать по X копии, повёрнутые \"спиной\" (angle > 90°)")]
    public bool mirrorBackside = true;

    public TrailTransform GetTransform(float age)
    {
        float angle = startAngleDeg * Mathf.Deg2Rad + age * turns * Mathf.PI * 2f;
        float s = Mathf.Sin(angle);
        float c = Mathf.Cos(angle); // 1 = лицом к зрителю, -1 = спиной

        var t = new TrailTransform
        {
            uvOffset = new Vector2(s * radius, c * verticalWobble)
        };

        float xScale = Mathf.Lerp(1f, Mathf.Abs(c), foreshorten);
        xScale = Mathf.Max(xScale, 0.15f); // не даём схлопнуться в ноль — пропадут пиксели
        t.uvScale = new Vector2(xScale, 1f);

        float depthFactor = (c + 1f) * 0.5f; // 0 = максимально "дальше", 1 = максимально "ближе"
        t.depthAlpha = Mathf.Lerp(1f - depthDim, 1f, depthFactor);

        t.mirror = mirrorBackside && c < 0f;

        return t;
    }

    public float SortDepth(float age)
    {
        float angle = startAngleDeg * Mathf.Deg2Rad + age * turns * Mathf.PI * 2f;
        return Mathf.Cos(angle);
    }
}
