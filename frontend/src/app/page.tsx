const phases = [
  "Phase 0: backend-first scaffold",
  "Phase 1: Mini-Claw backend baseline",
  "Phase 2: Skill Gateway MVP",
  "Phase 3: Skill Draft MVP",
];

export default function HomePage() {
  return (
    <main
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        padding: "32px",
      }}
    >
      <section
        style={{
          width: "min(880px, 100%)",
          borderRadius: "24px",
          padding: "32px",
          background: "rgba(255, 255, 255, 0.78)",
          backdropFilter: "blur(18px)",
          boxShadow: "0 24px 80px rgba(15, 23, 42, 0.12)",
        }}
      >
        <p style={{ letterSpacing: "0.12em", textTransform: "uppercase" }}>
          ClawForge
        </p>
        <h1 style={{ marginTop: "8px", fontSize: "clamp(2rem, 4vw, 3.5rem)" }}>
          Backend-first development is underway.
        </h1>
        <p style={{ fontSize: "1.1rem", lineHeight: 1.7, maxWidth: "60ch" }}>
          This UI is intentionally minimal for Phase 0. The core delivery focus
          is the backend runtime, skill gateway, draft pipeline, and governance
          workflow.
        </p>
        <ul style={{ marginTop: "24px", paddingLeft: "20px", lineHeight: 1.8 }}>
          {phases.map((phase) => (
            <li key={phase}>{phase}</li>
          ))}
        </ul>
      </section>
    </main>
  );
}
