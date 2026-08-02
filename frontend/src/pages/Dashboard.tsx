export function Dashboard() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Dashboard</h1>
      <p className="text-gray-600 dark:text-gray-400">
        Training overview and key metrics will appear here.
      </p>
      <div className="mt-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="text-sm text-gray-500 dark:text-gray-400">CTL (Fitness)</div>
          <div className="text-2xl font-bold text-gray-900 dark:text-white">--</div>
        </div>
        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="text-sm text-gray-500 dark:text-gray-400">ATL (Fatigue)</div>
          <div className="text-2xl font-bold text-gray-900 dark:text-white">--</div>
        </div>
        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="text-sm text-gray-500 dark:text-gray-400">TSB (Form)</div>
          <div className="text-2xl font-bold text-gray-900 dark:text-white">--</div>
        </div>
      </div>
    </div>
  );
}
