Shader "Kinekt/OutlineComposite"
{
    Properties
    {
        _MainTex ("Live Mask", 2D) = "white" {}
        _OutlineColor ("Outline Color", Color) = (1, 1, 1, 1)
        _OutlineWidth ("Outline Width", float) = 3
        _FadePower ("Fade Power", float) = 1.5
        _DriftAmount ("Drift Amount", float) = 0.02
        _HueShift ("Hue Shift", float) = 0.0
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
            float _Age;          // 0 = fresh, 1 = oldest
            float _SnapshotAlpha;

            v2f vert (appdata v)
            {
                v2f o;
                float2 drift = _DriftAmount * _Age * float2(1, -0.3);
                v.vertex.xy += drift;
                o.vertex = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                return o;
            }

            fixed4 frag (v2f i) : SV_Target
            {
                float2 uv = i.uv;
                float4 src = tex2D(_MainTex, uv);

                // outline: compare to neighbors
                float w = _OutlineWidth * _MainTex_TexelSize.x;
                float edges = 0;
                edges += tex2D(_MainTex, uv + float2(-w, 0)).r;
                edges += tex2D(_MainTex, uv + float2(w, 0)).r;
                edges += tex2D(_MainTex, uv + float2(0, -w)).r;
                edges += tex2D(_MainTex, uv + float2(0, w)).r;
                edges *= 0.25;

                float isEdge = edges > 0.1 && src.r < 0.1;

                // alpha fade: older = more transparent
                float alpha = pow(1.0 - _Age, _FadePower) * _SnapshotAlpha;

                // hue shift over age
                float3 col = _OutlineColor.rgb;
                float hue = _HueShift * _Age;
                col = lerp(col, _OutlineColor.rgb + hue, 0.3);

                fixed4 result = fixed4(col, isEdge * alpha);
                return result;
            }
            ENDCG
        }
    }
}
