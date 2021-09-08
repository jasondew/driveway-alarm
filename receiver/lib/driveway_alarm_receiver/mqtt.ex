defmodule DrivewayAlarmReceiver.MQTT do
  def publish(topic, data) do
    Tortoise.publish(Tortoise, topic, data)
  end
end
