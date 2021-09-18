extern crate paho_mqtt as mqtt;

use chrono::{DateTime, TimeZone, Utc};
use influxdb::{Client, InfluxDbWriteable};
use std::{process, thread, time::Duration};

const TOPIC: &str = "driveway-alarm/transmission";
const QOS: i32 = 1;

#[derive(InfluxDbWriteable)]
struct Reading {
    time: DateTime<Utc>,
    battery_voltage: f32,
    sonar_voltage: i32,
    cpu_temperature: f32,
    case_temperature: f32,
    case_humidity: f32,
    rssi: i32,
    snr: i32,
}

async fn process(msg: &mqtt::Message, client: &Client) {
    if let Some(reading) = parse(msg) {
        publish(reading, client).await;
    }
}

fn parse(msg: &mqtt::Message) -> Option<Reading> {
    let message: String = msg.payload_str().into_owned();
    let front_fields: Vec<&str> = message.splitn(3, ",").collect();

    match front_fields[..] {
        [from, length, payload_and_back_fields] => {
            let back_fields: Vec<&str> = payload_and_back_fields.rsplitn(3, ",").collect();
            match back_fields[..] {
                [snr, rssi, payload] => {
                    let json: serde_json::Value = serde_json::from_str(payload).unwrap();
                    println!(
                        "MESSAGE (from={} length={} rssi={} snr={}): {}",
                        from, length, rssi, snr, json
                    );

                    if json["event"] == "telemetry" {
                        let timestamp: i32 = serde_json::from_value(json["timestamp"].clone())
                            .expect("unable to parse timestamp");
                        Some(Reading {
                            time: Utc.datetime_from_str(&timestamp.to_string(), "%s").unwrap(),
                            battery_voltage: serde_json::from_value(
                                json["battery_voltage"].clone(),
                            )
                            .unwrap(),
                            sonar_voltage: serde_json::from_value(json["sonar_voltage"].clone())
                                .unwrap(),
                            cpu_temperature: serde_json::from_value(
                                json["cpu_temperature"].clone(),
                            )
                            .unwrap(),
                            case_temperature: serde_json::from_value(
                                json["case_temperature"].clone(),
                            )
                            .unwrap(),
                            case_humidity: serde_json::from_value(json["case_humidity"].clone())
                                .unwrap(),
                            rssi: rssi.parse().unwrap(),
                            snr: snr.parse().unwrap(),
                        })
                    } else {
                        None
                    }
                }
                _ => {
                    println!("INVALID MESSAGE: {}", message);
                    None
                }
            }
        }
        _ => {
            println!("INVALID MESSAGE: {}", message);
            None
        }
    }
}

async fn publish(reading: Reading, client: &Client) {
    let write_result = client.query(&reading.into_query("readings")).await;
    assert!(write_result.is_ok(), "Couldn't write data to InfluxDB");
}

fn try_reconnect(cli: &mqtt::Client) -> bool {
    println!("Connection lost. Waiting to retry connection");
    for _ in 0..12 {
        thread::sleep(Duration::from_millis(5000));
        if cli.reconnect().is_ok() {
            println!("Successfully reconnected");
            return true;
        }
    }
    println!("Unable to reconnect after several attempts.");
    false
}

fn subscribe(cli: &mqtt::Client) {
    if let Err(e) = cli.subscribe(TOPIC, QOS) {
        println!("Error subscribes topics: {:?}", e);
        process::exit(1);
    }
}

#[tokio::main]
async fn main() {
    let influxdb = Client::new("http://piplus.local:8086", "driveway_alarm");
    let create_opts = mqtt::CreateOptionsBuilder::new()
        .server_uri("tcp://piplus.local:1883")
        .client_id("driveway_alarm_processor")
        .finalize();

    // Create a client.
    let mut cli = mqtt::Client::new(create_opts).unwrap_or_else(|err| {
        println!("Error creating the client: {:?}", err);
        process::exit(1);
    });

    // Initialize the consumer before connecting.
    let receiver = cli.start_consuming();

    // Define the set of options for the connection.
    let conn_opts = mqtt::ConnectOptionsBuilder::new()
        .keep_alive_interval(Duration::from_secs(20))
        .clean_session(false)
        .finalize();

    // Connect and wait for it to complete or fail.
    if let Err(e) = cli.connect(conn_opts) {
        println!("Unable to connect:\n\t{:?}", e);
        process::exit(1);
    }

    // Subscribe topics.
    subscribe(&cli);

    println!("Processing requests...");
    for msg in receiver.iter() {
        if let Some(msg) = msg {
            process(&msg, &influxdb).await;
        } else if !cli.is_connected() {
            if try_reconnect(&cli) {
                println!("Resubscribe topics...");
                subscribe(&cli);
            } else {
                break;
            }
        }
    }

    // If still connected, then disconnect now.
    if cli.is_connected() {
        println!("Disconnecting");
        cli.unsubscribe(TOPIC).unwrap();
        cli.disconnect(None).unwrap();
    }
    println!("Exiting");
}
