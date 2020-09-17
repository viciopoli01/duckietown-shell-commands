
setup_etc_hosts() {
cat >/etc/hosts <<EOL
127.0.0.1	localhost
127.0.0.1	$(cat /etc/hostname)

# The following lines are desirable for IPv6 capable hosts
::1     ip6-localhost ip6-loopback
fe00::0 ip6-localnet
ff00::0 ip6-mcastprefix
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
EOL
}

run_on_first_boot () {
  echo "Setting up the robot for its first ever boot..."

  # sudo without a password
  echo "duckie ALL=(ALL) NOPASSWD:ALL" | tee -a /etc/sudoers

  # install wifi driver
  dkms add -m rtl88x2bu -v 5.6.1
  dkms build -m rtl88x2bu -v 5.6.1
  dkms install -m rtl88x2bu -v 5.6.1

  # install camera drivers
  cd /usr/src/linux-headers-4.9.140-tegra-ubuntu18.04_aarch64/kernel-4.9/v4l2loopback
  find . -exec touch \{\} \;
  make
  make install
  depmod -a
  modprobe v4l2loopback devices=1 video_nr=2 exclusive_caps=1
  update-initramfs -u

  # setup ssh access
  echo "Setting up ssh..."
  mkdir -p /home/duckie/.ssh
  touch /home/duckie/.ssh/authorized_keys
  echo "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDFiaiFeU0Pc3ZjiGbjJOIx28ghcWPoem8jU1OSeJnbTkKT79vrzjIbYjkBg7uBlXb6kLnbHLWHUnPlLk2IUQTxHHvakubEJkJxePdN6XO+q1sKpEvz+1GL60iBKhRljCZ9h/CcJ78kkyNQkexHT15ZDMhOnUd8c9zxwUHxSjzPSOH5ns8bxjU3oSjmzDEojPnQJmY6Evhf5DVcKXenxkzs4XgDEo+ldKo37i30iUoFCL30OsXCP2tPcn1j39qjL7vnaUBO9WqY8eOssOHAX7/K1dNN1lDvNCKspq/2f05Ss8LopSpe6hOiMnPB0RlotJbZn+784kV1B4nJpqLj+EQr DT2018key" | tee -a /home/duckie/.ssh/authorized_keys
  chmod 700 /home/duckie/.ssh
  chmod 600 /home/duckie/.ssh/authorized_keys
  chown -R duckie:duckie /home/duckie/.ssh

  # setup docker
  echo "Adding the user to the docker group..."
  adduser duckie docker

  # make sure the user owns its folders
  echo "Changing the ownership of the user directories..."
  chown -R 1000:1000 /data /code /home/duckie/

  # create swap
  echo "Setting up swap..."
  dd if=/dev/zero of=/swap0 bs=1M count=2048
  mkswap /swap0
  echo "/swap0 swap swap" >> /etc/fstab
  chmod 0600 /swap0
  swapon -a

  # store the MAC addresses for future reference
  echo "Storing debug information..."
  cp /proc/*info /data/proc
  cat /sys/class/net/eth0/address > /data/stats/MAC/eth0
  cat /sys/class/net/wlan0/address > /data/stats/MAC/wlan0

  echo "Setting up the containers..."
  setup_etc_hosts
  dt-autoboot

  echo "Setting up completed!"
}

run_on_every_boot () {
  echo "Setting up the robot for this boot..."

  setup_etc_hosts

  # while ! ifconfig wlan0
  # do
  #   echo "Waiting for wlan0 to show up..."
  #   sleep 1
  # done

  # sleep 1
  # killall wpa_supplicant
  # wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant.conf

  echo "Setting up completed!"
}

FIRST_BOOT_EVIDENCE_FILE="/etc/DT_FIRST_BOOT_EVIDENCE"
if test -f "$FIRST_BOOT_EVIDENCE_FILE"; then
  echo "$FIRST_BOOT_EVIDENCE_FILE exists so we assume this is not the first boot!"
  run_on_every_boot 2>&1 | tee /data/logs/this_boot_init.log
else
  echo "$FIRST_BOOT_EVIDENCE_FILE does not exist so we assume this is the first boot!"
  run_on_first_boot 2>&1 | tee /data/logs/first_boot_init.log
  touch "$FIRST_BOOT_EVIDENCE_FILE"
  reboot
fi

