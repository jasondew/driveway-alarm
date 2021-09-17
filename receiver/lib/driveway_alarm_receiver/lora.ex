defmodule DrivewayAlarmReceiver.Lora do
  use GenServer

  require Logger

  alias Nerves.UART

  @setup_delay_in_ms 5_000
  @wait_after_send_in_ms 100
  @wait_before_retry_in_ms 1000
  @timeout_in_ms 5_000
  @max_tries 3

  def start_link(opts) do
    GenServer.start_link(__MODULE__, opts, name: __MODULE__)
  end

  def send_data(address, data) do
    GenServer.call(__MODULE__, {:send_data, address, data})
  end

  @impl true
  def init(_opts) do
    info("starting...")
    Process.send_after(self(), :setup, @setup_delay_in_ms)

    {:ok, %{}}
  end

  @impl true
  def handle_call({:send_data, address, data}, _from, %{pid: pid} = state) do
    {:reply, send_data(pid, address, data), state}
  end

  @impl true
  def handle_info(:setup, _state) do
    pid = setup_connection("ttyAMA0", 3, 2)

    {:noreply, %{pid: pid}}
  end

  def handle_info({:nerves_uart, _, message}, state) do
    info("received data: #{inspect(message)}")

    handle_message(message)

    {:noreply, state}
  end

  def handle_info(message, state) do
    info("received message: #{inspect(message)}")
    {:noreply, state}
  end

  ## PRIVATE FUNCTIONS

  defp handle_message("+RCV=" <> message) do
    [from_address, _length, rest] = String.split(message, ",", parts: 3)

    [snr, rssi, payload] =
      rest
      |> String.reverse()
      |> String.split(",", parts: 3)
      |> Enum.map(&String.reverse/1)

    Task.start(fn ->
      DrivewayAlarmReceiver.handle(%{
        from_address: from_address,
        message: message,
        payload: payload,
        snr: snr,
        rssi: rssi
      })
    end)
  end

  defp handle_message(_payload), do: :ok

  defp setup_connection(device, network_id, address) do
    {:ok, pid} = UART.start_link()

    UART.open(pid, device,
      speed: 115_200,
      active: true,
      framing: {UART.Framing.Line, separator: "\r\n"}
    )

    clear_read_queue()
    send_command(pid, "AT+FACTORY")
    send_command(pid, "AT+ADDRESS=#{address}")
    send_command(pid, "AT+NETWORKID=#{network_id}")

    pid
  end

  defp send_command(pid, command, tries_left \\ @max_tries) do
    info(~s|sent command "#{command}"|)
    clear_read_queue()
    UART.write(pid, command)
    :timer.sleep(@wait_after_send_in_ms)

    case {read_from_uart(), tries_left} do
      {{:error, :no_response}, 0} ->
        {:error, :unable_to_send_command}

      {{:error, :no_response}, _tries_left} ->
        :timer.sleep(@wait_before_retry_in_ms)
        send_command(pid, command, tries_left - 1)

      {{:ok, "+ERR" <> _rest}, _tries_left} ->
        :timer.sleep(@wait_before_retry_in_ms)
        send_command(pid, command, tries_left - 1)

      {{:ok, _response}, _tries_left} ->
        :ok
    end
  end

  defp send_data(pid, address, data) do
    send_command(pid, "AT+SEND=#{address},#{String.length(data)},#{data}")
  end

  defp clear_read_queue() do
    receive do
      {:nerves_uart, _, _} -> clear_read_queue()
    after
      0 -> :ok
    end
  end

  defp read_from_uart() do
    receive do
      {:nerves_uart, _, response} ->
        info(~s|received response "#{response}"|)
        {:ok, response}
    after
      @timeout_in_ms ->
        info("no response received")
        {:error, :no_response}
    end
  end

  defp info(message) do
    Logger.info("[DrivewayAlarmReceiver] #{message}")
  end
end
