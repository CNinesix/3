#!/usr/bin/env bash
# nested-proxmox-setup.sh
# Provision a "Proxmox inside Proxmox" (nested) VM on an HP server that is
# already running Proxmox VE. This is the outer-host step of the th2 USB flow:
# the USB installs Proxmox on the HP server, then this script carves out a
# nested Proxmox VM that will run the VPN-for-mobile service (see ../vpn-mobile).
#
# RUN THIS ON THE OUTER PROXMOX HOST (the HP server), as root.
#
# It will:
#   1. Enable nested virtualization (Intel VT-x / AMD-V) on the host.
#   2. Create a VM sized to run Proxmox VE, with CPU type 'host' so the inner
#      Proxmox can itself run KVM guests.
#   3. Attach the Proxmox VE installer ISO you point it at.
#
# It does NOT auto-install Proxmox inside the VM (that needs the interactive
# installer, or a preseed you provide). It stops at "boot the VM and install".
#
# Usage:
#   ./nested-proxmox-setup.sh --iso local:iso/proxmox-ve_8.iso [options]
#
# Options (with defaults):
#   --vmid   9000                VM id for the nested Proxmox
#   --name   nested-pve          VM name
#   --cores  4                   vCPUs
#   --mem    8192                RAM in MB (Proxmox wants >= 2048; 8192 recommended)
#   --disk   64                  system disk size in GB
#   --storage local-lvm          storage for the VM disk
#   --bridge  vmbr0              network bridge
#   --iso    (required)          ISO volume id, e.g. local:iso/proxmox-ve_8.iso
#   --start                      start the VM after creating it
#   --dry-run                    print the qm commands without running them

set -euo pipefail

VMID=9000
NAME="nested-pve"
CORES=4
MEM=8192
DISK=64
STORAGE="local-lvm"
BRIDGE="vmbr0"
ISO=""
DO_START=0
DRY_RUN=0

die() { echo "error: $*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --vmid)    VMID="$2"; shift 2 ;;
    --name)    NAME="$2"; shift 2 ;;
    --cores)   CORES="$2"; shift 2 ;;
    --mem)     MEM="$2"; shift 2 ;;
    --disk)    DISK="$2"; shift 2 ;;
    --storage) STORAGE="$2"; shift 2 ;;
    --bridge)  BRIDGE="$2"; shift 2 ;;
    --iso)     ISO="$2"; shift 2 ;;
    --start)   DO_START=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
    *) die "unknown option: $1 (try --help)" ;;
  esac
done

run() {
  echo "+ $*"
  if [ "$DRY_RUN" -eq 0 ]; then
    "$@"
  fi
}

# --- sanity checks ------------------------------------------------------------
[ "$DRY_RUN" -eq 1 ] || [ "$(id -u)" -eq 0 ] || die "must run as root on the Proxmox host"
[ -n "$ISO" ] || die "--iso is required (e.g. --iso local:iso/proxmox-ve_8.iso)"

if [ "$DRY_RUN" -eq 0 ]; then
  command -v qm >/dev/null 2>&1 || die "qm not found - is this a Proxmox VE host?"
  if qm status "$VMID" >/dev/null 2>&1; then
    die "VMID $VMID already exists; pick another with --vmid"
  fi
fi

# --- 1. enable nested virtualization on the host ------------------------------
enable_nested() {
  local vendor conf module flag
  vendor=$(grep -m1 -o -E 'vmx|svm' /proc/cpuinfo || true)
  case "$vendor" in
    vmx) module="kvm_intel"; conf="/etc/modprobe.d/kvm-intel.conf" ;;
    svm) module="kvm_amd";   conf="/etc/modprobe.d/kvm-amd.conf" ;;
    *)
      if [ "$DRY_RUN" -eq 1 ]; then
        echo "note: this CPU does not report vmx/svm (fine for --dry-run;"
        echo "      on the real host, enable virtualization in BIOS). Assuming Intel."
        module="kvm_intel"; conf="/etc/modprobe.d/kvm-intel.conf"
      else
        die "CPU does not report VT-x (vmx) or AMD-V (svm); enable virtualization in BIOS"
      fi
      ;;
  esac

  # already on?
  flag=$(cat "/sys/module/${module}/parameters/nested" 2>/dev/null || echo "")
  if [ "$flag" = "Y" ] || [ "$flag" = "1" ]; then
    echo "nested virtualization already enabled for $module"
    return 0
  fi

  echo "enabling nested virtualization for $module"
  run sh -c "echo 'options ${module} nested=1' > '$conf'"
  # try a live reload; if the module is busy this needs a reboot instead
  if [ "$DRY_RUN" -eq 0 ]; then
    if ! (modprobe -r "$module" 2>/dev/null && modprobe "$module" 2>/dev/null); then
      echo "note: could not reload $module live (VMs running?). Reboot the host"
      echo "      to activate nested virtualization, then re-run with --start."
    fi
  else
    echo "+ modprobe -r $module && modprobe $module   # (or reboot)"
  fi
}
enable_nested

# --- 2. create the nested Proxmox VM ------------------------------------------
# CPU type 'host' is required so the inner Proxmox sees vmx/svm and can run KVM.
run qm create "$VMID" \
  --name "$NAME" \
  --cores "$CORES" \
  --cpu host \
  --memory "$MEM" \
  --net0 "virtio,bridge=${BRIDGE}" \
  --scsihw virtio-scsi-single \
  --ostype l26 \
  --machine q35 \
  --bios ovmf \
  --efidisk0 "${STORAGE}:1,efitype=4m,pre-enrolled-keys=0"

run qm set "$VMID" --scsi0 "${STORAGE}:${DISK},ssd=1"
run qm set "$VMID" --ide2 "${ISO},media=cdrom"
run qm set "$VMID" --boot "order=ide2;scsi0"
# larger balloon disabled: Proxmox dislikes ballooning
run qm set "$VMID" --balloon 0

echo ""
echo "Nested Proxmox VM $VMID ($NAME) created."
echo "  cores=$CORES  mem=${MEM}MB  disk=${DISK}G  storage=$STORAGE  bridge=$BRIDGE"
echo "  iso=$ISO"

if [ "$DO_START" -eq 1 ]; then
  run qm start "$VMID"
  echo "Started. Open the console:  qm terminal $VMID   (or the web UI console)"
else
  echo "Start it with:  qm start $VMID"
fi

cat <<EOF

Next steps:
  1. Open the VM console and run the Proxmox VE installer from the ISO.
  2. Give the inner node an IP on your $BRIDGE network.
  3. Inside the inner Proxmox, clone this repo and run the mobile VPN setup:
       git clone <this-repo> && sh 3/vpn-mobile/autorun-usb.sh
     so the nested node serves the VPN-for-mobile configs.

Tip: run with --dry-run first to review the exact qm commands.
EOF
