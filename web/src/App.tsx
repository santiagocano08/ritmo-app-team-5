// Console shell only. Screens (source status, fleet panel, recommendations) come from spec 003
// and read the backend API; this component holds no data and no access-control logic.
function App() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <h1 className="text-xl font-semibold">PulsoFlota</h1>
        <p className="text-sm text-slate-600">Consola del despachador · Corredor C6-008 (Prado)</p>
      </header>
      <main className="px-6 py-8">
        <p className="text-slate-600">Las pantallas de la consola se agregan con la spec 003.</p>
      </main>
    </div>
  )
}

export default App
