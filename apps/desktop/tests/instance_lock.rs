use crewden_desktop::config::InstanceLock;

// Run apart from the seed tests. A concurrent fork can inherit an open flock
// descriptor until exec and briefly retain the lock after the parent drops it.
#[test]
fn instance_lock_releases_on_drop() {
    let tmp = tempfile::tempdir().unwrap();
    let path = tmp.path().join("instance.lock");
    let lock = InstanceLock::try_acquire(&path).unwrap().unwrap();
    assert!(InstanceLock::try_acquire(&path).unwrap().is_none());
    drop(lock);
    assert!(InstanceLock::try_acquire(&path).unwrap().is_some());
}
