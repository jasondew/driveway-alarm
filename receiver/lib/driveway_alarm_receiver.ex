defmodule DrivewayAlarmReceiver do
  alias DrivewayAlarmReceiver.MQTT

  # "+RCV=2,24,1577866635:33296:34.1605,-48,51"
  def process("+RCV=" <> payload) do
    MQTT.publish("driveway-alarm/transmission", payload)
  end

  def process(_data), do: :ok
end
