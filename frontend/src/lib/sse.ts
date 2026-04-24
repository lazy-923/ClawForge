export type SseEvent = {
  event: string;
  data: unknown;
};

export function parseSseBuffer(input: string): { events: SseEvent[]; buffer: string } {
  const chunks = input.split("\n\n");
  const buffer = chunks.pop() ?? "";
  const events: SseEvent[] = [];

  for (const chunk of chunks) {
    const lines = chunk.split("\n");
    const eventLine = lines.find((line) => line.startsWith("event: "));
    const dataLine = lines.find((line) => line.startsWith("data: "));
    if (!eventLine || !dataLine) {
      continue;
    }

    events.push({
      event: eventLine.replace("event: ", "").trim(),
      data: JSON.parse(dataLine.replace("data: ", "")),
    });
  }

  return { events, buffer };
}
