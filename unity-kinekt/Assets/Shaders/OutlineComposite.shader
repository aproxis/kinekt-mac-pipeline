Shader "Kinekt/OutlineComposite"
{
    Properties
    {
        _MainTex ("Mask", 2D) = "white" {}
        _OutlineColor ("Outline Color", Color) = (0, 1, 1, 1)
        _OutlineWidth ("Outline Width", Float) = 3
        _FadePower ("Fade Power", Float) = 1.5
        _HueShift ("Hue Shift", Float) = 0.3
        _Age ("Age", Float) = 0
        _UVOffset ("UV Offset", Vector) = (0, 0, 0, 0)
        _UVScale ("UV Scale", Vector) = (1, 1, 0, 0)
        _Mirror ("Mirror", Float) = 0
        _TrailAlpha ("Trail Alpha", Float) = 1
        _LiveAlpha ("Live Alpha", Float) = 1
        _LiveIsOutline ("Live Is Outline", Float) = 0
    }

    SubShader
    {
        Tags { "Queue"="Transparent" "RenderType"="Transparent" }
        Blend SrcAlpha OneMinusSrcAlpha
        ZWrite Off
        Cull Off

        // ---- Pass 0: живой кадр — сплошная заливка или контур (переключает _LiveIsOutline) ----
        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            struct appdata { float4 vertex : POSITION; float2 uv : TEXCOORD0; };
            struct v2f { float2 uv : TEXCOORD0; float4 vertex : SV_POSITION; };

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

                if (_LiveIsOutline < 0.5)
                {
                    return fixed4(1, 1, 1, mask * _LiveAlpha);
                }

                float w = _OutlineWidth * _MainTex_TexelSize.x;
                float n  = tex2D(_MainTex, i.uv + float2(-w, 0)).r;
                float e  = tex2D(_MainTex, i.uv + float2( w, 0)).r;
                float s  = tex2D(_MainTex, i.uv + float2(0, -w)).r;
                float n2 = tex2D(_MainTex, i.uv + float2(0,  w)).r;
                float avg = (n + e + s + n2) * 0.25;
                float isEdge = (avg > 0.05 && mask < 0.05) ? 1.0 : 0.0;

                return fixed4(_OutlineColor.rgb, isEdge * _LiveAlpha);
            }
            ENDCG
        }

        // ---- Pass 1: трейл. Геометрию (offset/scale/mirror) полностью считает C#
        // (OutlineCompositor + опционально TrailCarousel) — здесь только применяем её
        // и рисуем контур. Так добавлять новые "пост-обработки" можно без правки шейдера. ----
        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            struct appdata { float4 vertex : POSITION; float2 uv : TEXCOORD0; };
            struct v2f { float2 uv : TEXCOORD0; float4 vertex : SV_POSITION; };

            sampler2D _MainTex;
            float4 _MainTex_TexelSize;
            fixed4 _OutlineColor;
            float _OutlineWidth;
            float _FadePower;
            float _HueShift;
            float _Age;
            float4 _UVOffset;
            float4 _UVScale;
            float _Mirror;
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
                float2 centered = i.uv - 0.5;
                centered.x *= (_Mirror > 0.5) ? -1.0 : 1.0;
                centered *= _UVScale.xy;
                float2 uv = centered + 0.5 + _UVOffset.xy;

                float mask = tex2D(_MainTex, uv).r;

                float w = _OutlineWidth * _MainTex_TexelSize.x;
                float n  = tex2D(_MainTex, uv + float2(-w, 0)).r;
                float e  = tex2D(_MainTex, uv + float2( w, 0)).r;
                float s  = tex2D(_MainTex, uv + float2(0, -w)).r;
                float n2 = tex2D(_MainTex, uv + float2(0,  w)).r;
                float avg = (n + e + s + n2) * 0.25;
                float isEdge = (avg > 0.05 && mask < 0.05) ? 1.0 : 0.0;

                float ageC = saturate(_Age);
                float alpha = pow(1.0 - ageC, _FadePower) * _TrailAlpha;

                float3 col = _OutlineColor.rgb;
                float3 alt = _OutlineColor.rgb + _HueShift * ageC * float3(0.5, -0.3, 0.8);
                col = lerp(col, alt, ageC);

                // за пределами кадра после смещения/скейла — не рисуем, иначе будут повторы по краям
                float inBounds = (uv.x >= 0 && uv.x <= 1 && uv.y >= 0 && uv.y <= 1) ? 1.0 : 0.0;

                return fixed4(col, isEdge * alpha * inBounds);
            }
            ENDCG
        }
    }
}
