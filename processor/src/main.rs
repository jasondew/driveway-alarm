extern crate paho_mqtt as mqtt;

use std::{process, thread, time::Duration};

const TOPIC: &str = "driveway-alarm/transmission";
const QOS: i32 = 1;

fn process(msg: &mqtt::Message) {
    let message: String = msg.payload_str().into_owned();
    let fields: Vec<&str> = message.split(",").collect();

    // 1,26,1578190458:4.10109:31.8198,-35,46
    match fields[..] {
        [from, length, payload, rssi, snr] => {
            let data: Vec<&str> = payload.split(":").collect();

            match data[..] {
                [timestamp, battery_voltage, cpu_temperature] =>
                    println!(
                        "MESSAGE (from={} length={} rssi={} snr={}): timestamp={} battery_voltage={} cpu_temperature={}",
                        from, length, rssi, snr, timestamp, battery_voltage, cpu_temperature
                    ),
                _ =>
                    println!(
                        "INVALID PAYLOAD (from={} length={} rssi={} snr={}): {}",
                        from, length, rssi, snr, payload
                    ),
            }
        }
        _ => println!("INVALID MESSAGE: {}", message),
    }
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

fn main() {
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
            process(&msg);
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
