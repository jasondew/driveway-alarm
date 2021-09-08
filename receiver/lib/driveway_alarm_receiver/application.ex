defmodule DrivewayAlarmReceiver.Application do
  # See https://hexdocs.pm/elixir/Application.html
  # for more information on OTP Applications
  @moduledoc false

  use Application

  def start(_type, _args) do
    # See https://hexdocs.pm/elixir/Supervisor.html
    # for other strategies and supported options
    opts = [strategy: :one_for_one, name: DrivewayAlarmReceiver.Supervisor]

    children =
      [
        # Children for all targets
        # Starts a worker by calling: DrivewayAlarmReceiver.Worker.start_link(arg)
        # {DrivewayAlarmReceiver.Worker, arg},
        %{
          id: Tortoise,
          start: {
            Tortoise.Supervisor,
            :start_child,
            [
              [
                client_id: Tortoise,
                server: {Tortoise.Transport.Tcp, host: 'piplus.local', port: 1883},
                handler: {Tortoise.Handler.Logger, []}
              ]
            ]
          }
        },
        DrivewayAlarmReceiver.Lora
      ] ++ children(target())

    Supervisor.start_link(children, opts)
  end

  # List all child processes to be supervised
  def children(:host) do
    [
      # Children that only run on the host
      # Starts a worker by calling: DrivewayAlarmReceiver.Worker.start_link(arg)
      # {DrivewayAlarmReceiver.Worker, arg},
    ]
  end

  def children(_target) do
    [
      # Children for all targets except host
      # Starts a worker by calling: DrivewayAlarmReceiver.Worker.start_link(arg)
      # {DrivewayAlarmReceiver.Worker, arg},
    ]
  end

  def target() do
    Application.get_env(:driveway_alarm_receiver, :target)
  end
end
