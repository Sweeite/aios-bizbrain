export default function CockpitHome() {
  return (
    <div className="p-8">
      <h2 className="text-2xl font-semibold">Cockpit</h2>
      <p className="mt-2 text-muted-foreground">
        Home screen — built in Slice 9.
      </p>
      <ul className="mt-6 space-y-2 text-sm text-muted-foreground">
        <li>Approval Queue — Slice 6</li>
        <li>Chat Interface — Slice 8</li>
        <li>Home / Today — Slice 9</li>
        <li>Activity Feed — Slice 14</li>
        <li>Client Profiles — Slice 15</li>
        <li>Integrations / Health — Slice 16</li>
        <li>Memory Browser — Slice 19</li>
        <li>Settings — Slice 20</li>
        <li>Audit Log — Slice 21</li>
        <li>Cost & ROI — Slice 22</li>
      </ul>
    </div>
  );
}
