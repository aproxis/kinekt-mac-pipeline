Shader "Kinekt/OutlineComposite"
{
    Properties
    {
        _MainTex ("Mask", 2D) = "white" {}
        _OutlineColor ("Outline Color", Color) = (0, 1, 1, 1)
        _OutlineWidth ("Outline Width", float) = 3
        _FadePower ("Fade Power", float) = 1.5
        _DriftAmount ("Drift Amount", float) = 0.02
        _DriftDirection ("Drift Direction", Vector) = (1, -0.3, 0, 0)
        _ScaleAmount ("Scale Amount", float) = 0
        _HueShift ("Hue Shift", float) = 0.3
        _Age ("Age", float) = 0
        _SnapshotAlpha ("Snapshot Alpha", float) = 1
        _LiveAlpha ("Live Alpha", float) = 1
        _TrailAlpha ("Trail Alpha", float) = 1
        _LiveIsOutline ("Live Is Outline", float) = 0
    }

    SubShader
    {
        Tags { "Queue"="Transparent" "RenderType"="Transparent" }
        Blend SrcAlpha OneMinusSrcAlpha
        ZWrite Off
        Cull Off

        // ---- Pass 0: живой силуэт / контур ----
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
            fixed4 _OutlineColor;
            float _OutlineWidth;
            float _LiveAlpha;
            float _LiveIsOutline;

            v2f vert (appdata v)
            {
                v2f o;
                o.vertex = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                return o;
            }

            fixed4 frag (v2f i) : SV_Target
            {
                float mask = tex2D(_MainTex, i.uv).r;

                if (_LiveIsOutline > 0.5)
                {
                    float w = _OutlineWidth * _MainTex_TexelSize.x;
                    float n = tex2D(_MainTex, i.uv + float2(-w, 0)).r;
                    float e = tex2D(_MainTex, i.uv + float2(w, 0)).r;
                    float s = tex2D(_MainTex, i.uv + float2(0, -w)).r;
                    float n2 = tex2D(_MainTex, i.uv + float2(0, w)).r;
                    float avg = (n + e + s + n2) * 0.25;
                    float isEdge = (avg > 0.05 && mask < 0.05) ? _LiveAlpha : 0;
                    return fixed4(_OutlineColor.rgb, isEdge);
                }
                else
                {
                    return fixed4(1, 1, 1, mask * _LiveAlpha);
                }
            }
            ENDCG
        }

        // ---- Pass 1: контур трейлов (снапшоты) ----
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
            float2 _DriftDirection;
            float _ScaleAmount;
            float _HueShift;
            float _Age;
            float _SnapshotAlpha;
            float _TrailAlpha;

            v2f vert (appdata v)
            {
                v2f o;
                o.vertex = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                return o;
            }

            fixed4 frag (v2f i) : SV_Target
            {
                // drift
                float2 uv = i.uv + _DriftAmount * _Age * _DriftDirection;

                // scale around center
                float2 center = float2(0.5, 0.5);
                uv = (uv - center) * (1 + _ScaleAmount * _Age) + center;

                float mask = tex2D(_MainTex, uv).r;

                // outline: 4-neighbor edge
                float w = _OutlineWidth * _MainTex_TexelSize.x;
                float n = tex2D(_MainTex, uv + float2(-w, 0)).r;
                float e = tex2D(_MainTex, uv + float2(w, 0)).r;
                float s = tex2D(_MainTex, uv + float2(0, -w)).r;
                float n2 = tex2D(_MainTex, uv + float2(0, w)).r;
                float avg = (n + e + s + n2) * 0.25;

                float isEdge = (avg > 0.05 && mask < 0.05) ? 1.0 : 0.0;

                // age=0 = newest (brightest), age=1 = oldest (most faded)
                float alpha = pow(1.0 - _Age, _FadePower) * _SnapshotAlpha * _TrailAlpha;

                // hue shift over age
                float3 col = _OutlineColor.rgb;
                float3 alt = _OutlineColor.rgb + _HueShift * _Age * float3(0.5, -0.3, 0.8);
                col = lerp(col, alt, _Age);

                return fixed4(col, isEdge * alpha);
            }
            ENDCG
        }
    }
}
