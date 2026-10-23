import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "#fbf7ee",
          position: "relative",
        }}
      >
        {/* duck face */}
        <div style={{ display: "flex", position: "relative", width: 160, height: 160, marginBottom: 32 }}>
          <div
            style={{
              position: "absolute",
              width: 160,
              height: 160,
              borderRadius: "50%",
              background: "#ffc93c",
              border: "8px solid #211d16",
            }}
          />
          <div
            style={{
              position: "absolute",
              left: 40,
              top: 92,
              width: 80,
              height: 40,
              borderRadius: "50%",
              background: "#ff7a3d",
              border: "6px solid #211d16",
            }}
          />
          <div style={{ position: "absolute", left: 48, top: 56, width: 18, height: 18, borderRadius: "50%", background: "#211d16" }} />
          <div style={{ position: "absolute", left: 94, top: 56, width: 18, height: 18, borderRadius: "50%", background: "#211d16" }} />
        </div>

        <div style={{ display: "flex", fontSize: 96, fontWeight: 800, color: "#211d16", letterSpacing: -2 }}>Duck</div>
        <div style={{ display: "flex", fontSize: 34, color: "#211d16", marginTop: 12, fontWeight: 600 }}>
          Explain the bug. <span style={{ background: "#ffc93c", padding: "0 8px", marginLeft: 8 }}>Out loud.</span>
        </div>
        <div style={{ display: "flex", fontSize: 22, color: "#ff7a3d", marginTop: 20, fontFamily: "monospace" }}>
          built voice-first with Wispr Flow
        </div>
      </div>
    ),
    { ...size }
  );
}
