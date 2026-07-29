import { useState, useEffect } from "react";

function App() {
  const [status, setStatus] = useState("checking...");

  useEffect(() => {
    fetch('http://localhost:8000/health')
      .then(res => res.json())
      .then(data => setStatus(data.status))
      .catch(err => setStatus("failed to connect"));

  }, []);

  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center">
      <h1 className="text-2xl font-bold text-white">Backend status: {status}</h1>
    </div>
  )
}

export default App;