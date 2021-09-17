defmodule DrivewayAlarmReceiver do
  alias DrivewayAlarmReceiver.{Lora, MQTT}

  @sensor_id 1

  def handle(%{payload: ~s|{"jsonrpc": "2.0", "method": "get_time"}|}) do
    now = DateTime.utc_now()
    day_of_week = Date.day_of_week(DateTime.to_date(now))

    Lora.send_data(
      @sensor_id,
      Jason.encode!(%{
        jsonrpc: "2.0",
        result:
          Enum.join(
            [
              now.year,
              now.month,
              now.day,
              now.hour,
              now.minute,
              now.second,
              day_of_week
            ],
            "-"
          )
      })
    )
  end

  def handle(%{message: message}) do
    MQTT.publish("driveway-alarm/transmission", message)
  end
end
