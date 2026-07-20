Shader "Kinekt/OutlineComposite"
{
    Properties
    {
        _MainTex ("Mask", 2D) = "white" {}
        _OutlineColor ("Outline Color", Color) = (0, 1, 1, 1)
        _OutlineWidth ("Outline Width", float) = 3
        _FadePower ("Fade Power", float) = 1.5
        _DriftAmount ("Drift Amount", float) = 0.02
        _HueShift ("Hue Shift", float) = 0.3
        _Age ("Age", float) = 0
        _SnapshotAlpha ("Snapshot Alpha", float) = 1
    }

    SubShader
    {
        Tags { "Queue"="Transparent" "RenderType"="Transparent" }
        Blend SrcAlpha OneMinusSrcAlpha
        ZWrite Off
        Cull Off

        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            struct appdata
            {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;
            };

            struct v2f
            {
                float2 uv : TEXCOORD0;
                float4 vertex : SV_POSITION;
            };

            sampler2D _MainTex;
            float4 _MainTex_TexelSize;
            float4 _OutlineColor;
            float _OutlineWidth;
            float _FadePower;
            float _DriftAmount;
            float _HueShift;
            float _Age;
            float _SnapshotAlpha;

            v2f vert (appdata v)
            {
                v2f o;
                o.vertex = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                return o;
            }

            fixed4 frag (v2f i) : SV_Target
            {
                // drift: old snapshots shift UV
                float2 uv = i.uv + _DriftAmount * _Age * float2(1, -0.3);

                float mask = tex2D(_MainTex, uv).r;

                // outline: sample 4 neighbors
                float w = _OutlineWidth * _MainTex_TexelSize.x;
                float n = tex2D(_MainTex, uv + float2(-w, 0)).r;
                float e = tex2D(_MainTex, uv + float2(w, 0)).r;
                float s = tex2D(_MainTex, uv + float2(0, -w)).r;
                float n2 = tex2D(_MainTex, uv + float2(0, w)).r;
                float avg = (n + e + s + n2) * 0.25;

                float isEdge = avg > 0.05 && mask < 0.05;

                // alpha fade: old = transparent
                float alpha = pow(1.0 - _Age, _FadePower) * _SnapshotAlpha;

                // hue shift
                float3 col = _OutlineColor.rgb;
                float3 alt = _OutlineColor.rgb + _HueShift * _Age * float3(0.5, -0.3, 0.8);
                col = lerp(col, alt, _Age);

                return fixed4(col, isEdge * alpha);
            }
            ENDCG
        }
    }
}
