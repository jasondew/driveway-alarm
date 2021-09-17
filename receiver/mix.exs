defmodule DrivewayAlarmReceiver.MixProject do
  use Mix.Project

  @app :driveway_alarm_receiver
  @version "0.1.0"

  def project do
    [
      app: @app,
      version: @version,
      elixir: "~> 1.9",
      archives: [nerves_bootstrap: "~> 1.10"],
      start_permanent: Mix.env() == :prod,
      build_embedded: true,
      deps: deps(),
      releases: [{@app, release()}],
      preferred_cli_target: [run: :host, test: :host]
    ]
  end

  # Run "mix help compile.app" to learn about applications.
  def application do
    [
      mod: {DrivewayAlarmReceiver.Application, []},
      extra_applications: [:logger, :runtime_tools]
    ]
  end

  # Run "mix help deps" to learn about dependencies.
  defp deps do
    [
      # Dependencies for all targets
      {:jason, "~> 1.2.2"},
      {:nerves, "~> 1.7.0", runtime: false},
      {:shoehorn, "~> 0.7.0"},
      {:ring_logger, "~> 0.8.1"},
      {:toolshed, "~> 0.2.13"},
      {:tortoise, "~> 0.9"},

      # target-only deps
      {:nerves_runtime, "~> 0.11.3", targets: :rpi0},
      {:nerves_pack, "~> 0.4.0", targets: :rpi0},
      {:nerves_uart, "~> 1.2", targets: :rpi0},
      {:nerves_leds, "~> 0.8", targets: :rpi0},
      {:nerves_system_rpi0, "~> 1.13", runtime: false, targets: :rpi0}
    ]
  end

  def release do
    [
      overwrite: true,
      # Erlang distribution is not started automatically.
      # See https://hexdocs.pm/nerves_pack/readme.html#erlang-distribution
      cookie: "#{@app}_cookie",
      include_erts: &Nerves.Release.erts/0,
      steps: [&Nerves.Release.init/1, :assemble],
      strip_beams: Mix.env() == :prod or [keep: ["Docs"]]
    ]
  end
end
