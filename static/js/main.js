document.addEventListener('DOMContentLoaded', function() {
    // 手机端侧边抽屉菜单
    const mobileAvatarBtn = document.getElementById('mobileAvatarBtn');
    const mobileDrawer = document.getElementById('mobileDrawer');
    const drawerBackdrop = document.getElementById('drawerBackdrop');
    const closeDrawerBtn = document.getElementById('closeDrawerBtn');

    if (mobileAvatarBtn && mobileDrawer && drawerBackdrop) {
        function openDrawer() {
            mobileDrawer.classList.add('active');
            drawerBackdrop.classList.add('active');
            document.body.style.overflow = 'hidden'; // 阻止背景滚动
        }

        function closeDrawer() {
            mobileDrawer.classList.remove('active');
            drawerBackdrop.classList.remove('active');
            document.body.style.overflow = '';
        }

        mobileAvatarBtn.addEventListener('click', openDrawer);
        drawerBackdrop.addEventListener('click', closeDrawer);
        if (closeDrawerBtn) {
            closeDrawerBtn.addEventListener('click', closeDrawer);
        }
    }

    // 交互微动画与状态模拟
    // 点赞模拟
    const likeButtons = document.querySelectorAll('.action-like');
    likeButtons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const icon = this.querySelector('i');
            const countSpan = this.querySelector('.like-count');
            let count = parseInt(countSpan.textContent) || 0;
            
            if (this.classList.contains('liked')) {
                this.classList.remove('liked');
                icon.className = 'bi bi-heart';
                countSpan.textContent = count - 1 > 0 ? count - 1 : '';
            } else {
                this.classList.add('liked');
                icon.className = 'bi bi-heart-fill text-danger';
                countSpan.textContent = count + 1;
            }
        });
    });

    // 转发模拟
    const repostButtons = document.querySelectorAll('.action-repost');
    repostButtons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const icon = this.querySelector('i');
            const countSpan = this.querySelector('.repost-count');
            let count = parseInt(countSpan.textContent) || 0;
            
            if (this.classList.contains('reposted')) {
                this.classList.remove('reposted');
                icon.className = 'bi bi-arrow-repeat';
                countSpan.textContent = count - 1 > 0 ? count - 1 : '';
            } else {
                this.classList.add('reposted');
                icon.className = 'bi bi-arrow-repeat text-success fw-bold';
                countSpan.textContent = count + 1;
            }
        });
    });

    // 评论模态框或发帖模态框触发器
    // 主要是悬浮 + 按钮拉起 Bootstrap 发帖 modal
    const mobileFab = document.getElementById('mobileFab');
    if (mobileFab) {
        mobileFab.addEventListener('click', function() {
            const postModalEl = document.getElementById('postModal');
            if (postModalEl) {
                const postModal = new bootstrap.Modal(postModalEl);
                postModal.show();
            }
        });
    }
});
