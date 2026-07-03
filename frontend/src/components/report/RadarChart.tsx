"use client";

interface RadarDataPoint {
  label: string;
  value: number;
}

interface RadarChartProps {
  data: RadarDataPoint[];
  maxValue?: number;
  size?: number;
  showLabels?: boolean;
}

export function RadarChart({
  data,
  maxValue = 5,
  size = 200,
  showLabels = true,
}: RadarChartProps) {
  const cx = size / 2;
  const cy = size / 2;
  const radius = size * 0.38;
  const levels = 5; // Number of grid rings (1-5)

  if (data.length < 3) return null;

  const angleSlice = (2 * Math.PI) / data.length;

  // Compute polygon points for a given set of values
  const getPoints = (values: number[]) => {
    return values
      .map((v, i) => {
        const r = (v / maxValue) * radius;
        const angle = i * angleSlice - Math.PI / 2;
        return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`;
      })
      .join(" ");
  };

  // Grid levels
  const gridRings = Array.from({ length: levels }, (_, i) => {
    const r = ((i + 1) / levels) * radius;
    return data
      .map((_, j) => {
        const angle = j * angleSlice - Math.PI / 2;
        return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`;
      })
      .join(" ");
  });

  // Axis lines
  const axes = data
    .map((_, i) => {
      const angle = i * angleSlice - Math.PI / 2;
      return `${cx},${cy} ${cx + radius * Math.cos(angle)},${cy + radius * Math.sin(angle)}`;
    })
    .join(" ");

  // Data polygon points
  const dataValues = data.map((d) => Math.max(0, Math.min(maxValue, d.value)));
  const dataPolygon = getPoints(dataValues);

  // Label positions (slightly outside the max ring)
  const labels = data.map((d, i) => {
    const angle = i * angleSlice - Math.PI / 2;
    const lr = radius + 18;
    const x = cx + lr * Math.cos(angle);
    const y = cy + lr * Math.sin(angle);
    const anchor =
      Math.abs(x - cx) < 10 ? "middle" : x > cx ? "start" : "end";
    return { x, y, anchor, label: d.label };
  });

  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      width={size}
      height={size}
      className="mx-auto"
      role="img"
      aria-label="Radar chart"
    >
      {/* Grid rings */}
      {gridRings.map((points, i) => (
        <polygon
          key={`ring-${i}`}
          points={points}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth={i === levels - 1 ? 1.5 : 0.5}
        />
      ))}

      {/* Axis lines */}
      {axes.split(" ").map((line, i) => {
        const [x1, y1, x2, y2] = line.split(/[, ]/).map(Number);
        return (
          <line
            key={`axis-${i}`}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke="#e5e7eb"
            strokeWidth={0.5}
          />
        );
      })}

      {/* Data polygon */}
      <polygon
        points={dataPolygon}
        fill="rgba(59, 130, 246, 0.15)"
        stroke="#3b82f6"
        strokeWidth={2}
        strokeLinejoin="round"
      />

      {/* Data points */}
      {dataValues.map((v, i) => {
        const angle = i * angleSlice - Math.PI / 2;
        const r = (v / maxValue) * radius;
        const x = cx + r * Math.cos(angle);
        const y = cy + r * Math.sin(angle);
        return (
          <circle
            key={`dot-${i}`}
            cx={x}
            cy={y}
            r={3}
            fill="#3b82f6"
            stroke="white"
            strokeWidth={1}
          />
        );
      })}

      {/* Labels */}
      {showLabels &&
        labels.map((l, i) => (
          <text
            key={`label-${i}`}
            x={l.x}
            y={l.y}
            textAnchor={l.anchor}
            dominantBaseline="middle"
            className="fill-gray-600"
            style={{ fontSize: 10 }}
          >
            {l.label}
          </text>
        ))}

      {/* Score labels on data points */}
      {showLabels &&
        dataValues.map((v, i) => {
          const angle = i * angleSlice - Math.PI / 2;
          const r = (v / maxValue) * radius;
          const x = cx + r * Math.cos(angle);
          const y = cy + r * Math.sin(angle) - 10;
          return (
            <text
              key={`score-${i}`}
              x={x}
              y={y}
              textAnchor="middle"
              className="fill-blue-700 font-semibold"
              style={{ fontSize: 9 }}
            >
              {v}
            </text>
          );
        })}
    </svg>
  );
}
